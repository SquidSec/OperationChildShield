"""Constituent accounts: registration, email verification, sign in, password reset.

There is no admin registration here; admin accounts stay in admin_store and are
seeded. This router only serves public site members.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app import users_store
from app.config import settings
from app.user_auth import (
    USER_COOKIE_NAME,
    clear_user_cookie,
    current_user,
    set_user_cookie,
    user_session_token,
)
from app.security import client_ip, rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

GENERIC_AUTH_ERROR = "Invalid email or password."


def _limit(max_hits: int) -> int:
    """Relax throttles for local manual testing when explicitly enabled."""
    return max_hits * 20 if settings.dev_relax_rate_limits else max_hits
_REGISTER_MESSAGE = (
    "Check your email for a link to finish creating your account."
)


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=1024)
    displayName: str = Field(default="", max_length=120)
    consent: bool = False

    @field_validator("email", "displayName")
    @classmethod
    def strip(cls, value: str) -> str:
        return (value or "").strip()


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("email")
    @classmethod
    def strip(cls, value: str) -> str:
        return (value or "").strip()


class TokenRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=512)


class PasswordResetRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)


class PasswordSetRequest(BaseModel):
    token: str = Field(..., min_length=10, max_length=512)
    password: str = Field(..., min_length=1, max_length=1024)


class SaveMemberRequest(BaseModel):
    bioguideId: str = Field(..., min_length=2, max_length=16)
    name: str = Field(default="", max_length=120)
    state: str = Field(default="", max_length=64)

    @field_validator("bioguideId", "name", "state")
    @classmethod
    def strip(cls, value: str) -> str:
        return (value or "").strip()


def _check_origin(request: Request) -> None:
    """Same-origin guard for cookie-authenticated writes."""
    fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if fetch_site == "same-origin":
        return
    if fetch_site in {"cross-site", "same-site"}:
        raise HTTPException(status_code=403, detail="Origin not allowed")
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        return
    if origin in set(settings.cors_origin_list):
        return
    from urllib.parse import urlsplit

    allowed = {(urlsplit(o).hostname or "").lower() for o in settings.cors_origin_list}
    if (urlsplit(origin).hostname or "").lower() in allowed:
        return
    raise HTTPException(status_code=403, detail="Origin not allowed")


def _cookie_secure(request: Request) -> bool:
    if settings.admin_cookie_secure:
        return True
    return request.url.scheme == "https" or (
        request.headers.get("x-forwarded-proto", "").lower() == "https"
    )


def _send_verification_email(email: str, token: str) -> str | None:
    """Email the verification link. Returns the link in dev-outbox mode."""
    from app.email_smtp import send_plain_email

    link = f"{settings.public_site_url.rstrip('/')}/account/verify?token={token}"
    if settings.dev_email_outbox:
        # Relative so the link works whichever local host the browser is on
        # (localhost vs 127.0.0.1 keep separate cookie jars).
        relative = f"/account/verify?token={token}"
        logger.warning("DEV OUTBOX: verification link for %s: %s", email, link)
        return relative
    if not settings.smtp_configured:
        # Local/dev: no mail server. Log the link so the flow stays testable.
        logger.warning("SMTP not configured; verification link for %s: %s", email, link)
        return None
    body = (
        "Welcome to Operation Child Shield.\n\n"
        "Confirm your email address to finish setting up your account:\n\n"
        f"{link}\n\n"
        "This link expires in 48 hours. If you did not create an account, ignore this email."
    )
    try:
        send_plain_email(email, "Confirm your Operation Child Shield account", body)
    except Exception:
        logger.exception("Failed to send verification email")
    return None


def _send_reset_email(email: str, token: str) -> str | None:
    """Email the reset link. Returns the link in dev-outbox mode."""
    from app.email_smtp import send_plain_email

    link = f"{settings.public_site_url.rstrip('/')}/account/reset?token={token}"
    if settings.dev_email_outbox:
        relative = f"/account/reset?token={token}"
        logger.warning("DEV OUTBOX: password reset link for %s: %s", email, link)
        return relative
    if not settings.smtp_configured:
        logger.warning("SMTP not configured; password reset link for %s: %s", email, link)
        return None
    body = (
        "We received a request to reset your Operation Child Shield password.\n\n"
        f"{link}\n\n"
        "This link expires in 2 hours. If you did not request a reset, ignore this email."
    )
    try:
        send_plain_email(email, "Reset your Operation Child Shield password", body)
    except Exception:
        logger.exception("Failed to send password reset email")
    return None


@router.post("/account/register")
async def register(body: RegisterRequest, request: Request):
    rate_limit(
        client_ip(request),
        bucket="account_register",
        max_hits=_limit(5),
        window_seconds=3600.0,
        detail="Too many signup attempts. Please try again later.",
    )
    if not body.consent:
        raise HTTPException(status_code=400, detail="Consent is required to create an account.")

    try:
        user = await asyncio.to_thread(
            users_store.create_user, body.email, body.password, body.displayName
        )
    except ValueError as exc:
        message = str(exc)
        if "already exists" in message:
            # Do not confirm which addresses exist.
            return {"ok": True, "message": _REGISTER_MESSAGE}
        raise HTTPException(status_code=400, detail=message)

    token = await asyncio.to_thread(
        users_store.create_token, int(user["id"]), "verify_email",
        ttl_hours=users_store.VERIFY_TTL_HOURS,
    )
    # Sending mail is blocking and can be slow; keep it off the event loop.
    loop = asyncio.get_running_loop()
    if settings.dev_email_outbox:
        # Dev-only: surface the link so the flow is testable without a mailbox.
        dev_link = await loop.run_in_executor(
            None, _send_verification_email, user["email"], token
        )
        return {"ok": True, "message": _REGISTER_MESSAGE, "devVerificationUrl": dev_link}
    loop.run_in_executor(None, _send_verification_email, user["email"], token)
    return {"ok": True, "message": _REGISTER_MESSAGE}


@router.post("/account/verify")
async def verify_email(body: TokenRequest, request: Request, response: Response):
    rate_limit(client_ip(request), bucket="account_verify", max_hits=20, window_seconds=3600.0)
    user_id = await asyncio.to_thread(users_store.consume_token, body.token, "verify_email")
    if user_id is None:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")

    await asyncio.to_thread(users_store.mark_email_verified, user_id)
    user = await asyncio.to_thread(users_store.get_user, user_id)
    if not user:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")

    from app.user_auth import create_user_session

    token = await asyncio.to_thread(create_user_session, user_id, client_ip(request))
    set_user_cookie(
        response, token, max_age_seconds=14 * 24 * 3600, secure=_cookie_secure(request)
    )
    return {"ok": True, "user": user}


@router.post("/account/login")
async def login(body: LoginRequest, request: Request, response: Response):
    ip = client_ip(request)
    rate_limit(ip, bucket="account_login_ip", max_hits=_limit(10), window_seconds=300.0,
               detail="Too many login attempts. Try again later.")
    _check_origin(request)

    user = await asyncio.to_thread(users_store.authenticate, body.email, body.password)
    if user is None:
        raise HTTPException(status_code=401, detail=GENERIC_AUTH_ERROR)
    if not user["emailVerified"]:
        raise HTTPException(
            status_code=403,
            detail="Confirm your email address before signing in.",
        )

    from app.user_auth import create_user_session

    token = await asyncio.to_thread(create_user_session, int(user["id"]), ip)
    set_user_cookie(
        response, token, max_age_seconds=14 * 24 * 3600, secure=_cookie_secure(request)
    )
    return {"ok": True, "user": user}


@router.post("/account/logout")
async def logout(request: Request, response: Response):
    _check_origin(request)
    from app.user_auth import delete_user_session

    await asyncio.to_thread(delete_user_session, user_session_token(request))
    clear_user_cookie(response)
    return {"ok": True}


@router.get("/account/me")
async def me(request: Request):
    user = current_user(request)
    return {"user": user, "savedMembers": _saved(int(user["id"]))}


def _saved(user_id: int) -> list[dict[str, str]]:
    return users_store.list_saved_members(user_id)


@router.post("/account/password/request")
async def request_password_reset(body: PasswordResetRequest, request: Request):
    rate_limit(
        client_ip(request), bucket="account_reset", max_hits=_limit(5), window_seconds=3600.0,
        detail="Too many reset requests. Please try again later.",
    )
    user = await asyncio.to_thread(users_store.get_user_by_email, body.email)
    # Always report success so the endpoint cannot enumerate accounts.
    if user and user["isActive"]:
        token = await asyncio.to_thread(
            users_store.create_token, int(user["id"]), "reset_password",
            ttl_hours=users_store.RESET_TTL_HOURS,
        )
        asyncio.get_running_loop().run_in_executor(
            None, _send_reset_email, user["email"], token
        )
    return {"ok": True, "message": "If that email has an account, a reset link is on its way."}


@router.post("/account/password/reset")
async def reset_password(body: PasswordSetRequest, request: Request):
    rate_limit(client_ip(request), bucket="account_reset_confirm", max_hits=10, window_seconds=3600.0)
    user_id = await asyncio.to_thread(users_store.consume_token, body.token, "reset_password")
    if user_id is None:
        raise HTTPException(status_code=400, detail="This link is invalid or has expired.")
    try:
        await asyncio.to_thread(users_store.set_password, user_id, body.password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    from app.user_auth import delete_sessions_for_user

    await asyncio.to_thread(delete_sessions_for_user, user_id)
    return {"ok": True, "message": "Password updated. You can sign in now."}


@router.get("/account/saved-members")
async def list_saved(request: Request):
    user = current_user(request)
    return {"members": _saved(int(user["id"]))}


@router.post("/account/saved-members")
async def add_saved(body: SaveMemberRequest, request: Request):
    _check_origin(request)
    user = current_user(request)
    try:
        await asyncio.to_thread(
            users_store.save_member,
            int(user["id"]),
            body.bioguideId.upper(),
            name=body.name,
            state=body.state,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "members": _saved(int(user["id"]))}


@router.delete("/account/saved-members/{bioguide_id}")
async def remove_saved(bioguide_id: str, request: Request):
    _check_origin(request)
    user = current_user(request)
    removed = await asyncio.to_thread(
        users_store.remove_saved_member, int(user["id"]), bioguide_id.upper()[:16]
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Not saved")
    return {"ok": True, "members": _saved(int(user["id"]))}


@router.get("/account/alerts")
async def list_alerts(request: Request):
    user = current_user(request)
    return {"alerts": users_store.list_alert_subscriptions(user["email"])}


class AlertRequest(BaseModel):
    kind: str = Field(..., min_length=3, max_length=40)
    bioguideId: str = Field(default="", max_length=16)


@router.post("/account/alerts")
async def create_alert(body: AlertRequest, request: Request):
    _check_origin(request)
    user = current_user(request)
    try:
        sub = await asyncio.to_thread(
            users_store.subscribe_alert,
            user["email"],
            body.kind,
            bioguide_id=body.bioguideId,
            user_id=int(user["id"]),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"ok": True, "subscription": sub}


@router.delete("/account/alerts/{kind}")
async def delete_alert(kind: str, request: Request, bioguideId: str = ""):
    _check_origin(request)
    user = current_user(request)
    users_store.unsubscribe_alert(user["email"], kind, bioguide_id=bioguideId)
    return {"ok": True, "alerts": users_store.list_alert_subscriptions(user["email"])}


# --- Public unsubscribe (no login required; link comes from email) ---------

@router.get("/alerts/unsubscribe")
async def unsubscribe(token: str):
    from app.alerts import verify_unsubscribe_token

    payload = verify_unsubscribe_token(token)
    if not payload:
        raise HTTPException(status_code=400, detail="This unsubscribe link is invalid.")
    removed = users_store.unsubscribe_all(payload["email"])
    return {"ok": True, "email": payload["email"], "removed": removed}


__all__ = ["router", "USER_COOKIE_NAME"]
