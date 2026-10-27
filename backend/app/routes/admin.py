"""Admin authentication, traffic dashboard, account management, and audit API.

No registration endpoint: accounts are seeded with scripts/seed_admin.py or
created by an owner. Every login failure returns the same generic message so the
endpoint cannot be used to enumerate accounts; lockouts are silent.
"""

from __future__ import annotations

import csv
import io
import logging
import re
import sqlite3
import time
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field, field_validator

from app import admin_jobs, admin_store, analytics_store, applications_store, backup
from app.admin_auth import (
    clear_session_cookie,
    current_admin,
    session_token,
    set_session_cookie,
)
from app.captcha import verify_turnstile
from app import passwords, qr
from app.config import settings
from app.security import client_ip, rate_limit

logger = logging.getLogger(__name__)
router = APIRouter()

GENERIC_LOGIN_ERROR = "Invalid email or password, or captcha verification failed."
MFA_REQUIRED = "OTP enrolment required"
# Password rules live in app.passwords (NIST SP 800-63B-4 aligned).
MIN_PASSWORD_LENGTH = passwords.MIN_PASSWORD_LENGTH

# Process start, for the health panel's uptime.
_STARTED_AT = time.time()


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    password: str = Field(..., min_length=1, max_length=1024)
    captcha_token: str = Field(default="", max_length=4096)
    mfa_code: str = Field(default="", max_length=16)

    @field_validator("email", "password", "captcha_token", "mfa_code")
    @classmethod
    def strip_fields(cls, value: str) -> str:
        return (value or "").strip()


class MFAVerifyRequest(BaseModel):
    code: str = Field(..., min_length=6, max_length=8)

    @field_validator("code")
    @classmethod
    def strip_code(cls, value: str) -> str:
        return (value or "").strip()


class PasswordChangeRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=1024)
    new_password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("new_password")
    @classmethod
    def enforce_policy(cls, value: str) -> str:
        try:
            return passwords.validate_password(value)
        except passwords.PasswordPolicyError as exc:
            raise ValueError(str(exc)) from exc


class CreateUserRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=254)
    display_name: str = Field(default="", max_length=120)
    password: str = Field(..., min_length=1, max_length=1024)
    role: str = Field(default=admin_store.DEFAULT_ROLE, max_length=16)

    @field_validator("password")
    @classmethod
    def enforce_policy(cls, value: str) -> str:
        try:
            return passwords.validate_password(value)
        except passwords.PasswordPolicyError as exc:
            raise ValueError(str(exc)) from exc

    @field_validator("role")
    @classmethod
    def check_role(cls, value: str) -> str:
        try:
            return admin_store.validate_role(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class RoleRequest(BaseModel):
    role: str = Field(..., max_length=16)

    @field_validator("role")
    @classmethod
    def check_role(cls, value: str) -> str:
        try:
            return admin_store.validate_role(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


# --- Shared helpers ----------------------------------------------------------


def require_role(request: Request, *roles: str) -> dict[str, object]:
    """Return the session admin when its role is one of ``roles``.

    Raises 401 when unauthenticated (handled by ``current_admin``) and 403 when
    the account exists but is not allowed to perform the action.
    """
    user = current_admin(request)
    role = str(user.get("role") or admin_store.DEFAULT_ROLE)
    if roles and role not in roles:
        raise HTTPException(status_code=403, detail="Insufficient role")
    return user


def require_mfa(user: dict[str, object]) -> None:
    """Gate sensitive endpoints when ADMIN_REQUIRE_MFA is on."""
    if settings.admin_require_mfa and not user.get("mfaEnabled"):
        raise HTTPException(status_code=403, detail=MFA_REQUIRED)


def _require_owner(request: Request) -> dict[str, object]:
    user = require_role(request, "owner")
    require_mfa(user)
    return user


def _audit_actor(user: dict[str, object]) -> str:
    return str(user.get("email") or "unknown")


def _check_origin(request: Request) -> None:
    """Reject cross-site state changes in addition to SameSite=Strict.

    Admin requests are proxied (Caddy in production, a Next rewrite in dev), so
    the backend may see the proxy's host rather than the browser's. Sec-Fetch-Site
    is set by the browser and cannot be forged from page scripts, so it is the
    primary signal; the Origin allowlist is the fallback for older clients.
    """
    fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if fetch_site == "same-origin":
        return
    if fetch_site in {"cross-site", "same-site"}:
        raise HTTPException(status_code=403, detail="Origin not allowed")

    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        return  # Non-browser clients (seeding, tests) send no Origin.
    if origin in set(settings.cors_origin_list):
        return

    from urllib.parse import urlsplit

    allowed_hosts = {
        (urlsplit(o).hostname or "").lower() for o in settings.cors_origin_list
    }
    origin_host = (urlsplit(origin).hostname or "").lower()
    if origin_host and origin_host in allowed_hosts:
        return

    raise HTTPException(status_code=403, detail="Origin not allowed")


def _cookie_secure(request: Request) -> bool:
    if settings.admin_cookie_secure:
        return True
    return request.url.scheme == "https" or (
        request.headers.get("x-forwarded-proto", "").lower() == "https"
    )


@router.get("/admin/config")
async def admin_config():
    """Public bootstrap config: lets the login page render the captcha widget."""
    return {
        "captchaRequired": settings.captcha_enforced,
        "captchaSiteKey": settings.turnstile_site_key or "",
        "captchaConfigured": bool(
            settings.turnstile_site_key and settings.turnstile_secret_key
        ),
        # OTP is mandatory for every account; the login UI reads this to decide
        # whether to show the enrolment notice.
        "otpRequired": True,
        "passwordRules": passwords.rules_for_display(),
    }


# --- Authentication ----------------------------------------------------------


@router.post("/admin/login")
async def admin_login(body: LoginRequest, request: Request, response: Response):
    ip = client_ip(request)
    # Two buckets: one slows credential stuffing across accounts, one slows
    # guessing against a single account from many IPs.
    rate_limit(ip, bucket="admin_login_ip", max_hits=10, window_seconds=300.0,
               detail="Too many login attempts. Try again in a few minutes.")
    # The per-account throttle sits above the lockout threshold (5) so a locked
    # account sees the actionable lockout message instead of a generic 429 that
    # would clear on its own while the lockout persisted.
    rate_limit(
        f"{ip}:{body.email.lower()}",
        bucket="admin_login_account",
        max_hits=20,
        window_seconds=300.0,
        detail="Too many login attempts. Try again in a few minutes.",
    )
    _check_origin(request)

    # Say the account is locked rather than "invalid credentials". The lockout
    # only triggers after repeated failures against a real account, so this does
    # not confirm whether an arbitrary email exists.
    locked_seconds = admin_store.lockout_remaining_seconds(body.email)
    if locked_seconds > 0:
        minutes = max(1, (locked_seconds + 59) // 60)
        admin_store.record_audit(
            body.email, "login_locked", f"{locked_seconds}s remaining", ip
        )
        raise HTTPException(
            status_code=429,
            detail=(
                f"Too many failed attempts. This account is locked for about "
                f"{minutes} more minute{'s' if minutes != 1 else ''}."
            ),
            headers={"Retry-After": str(locked_seconds)},
        )

    captcha_ok = await verify_turnstile(
        body.captcha_token, remote_ip=ip
    )
    if not captcha_ok:
        logger.info("Admin login captcha failure from %s", ip)
        raise HTTPException(status_code=400, detail=GENERIC_LOGIN_ERROR)

    user = await _authenticate(body.email, body.password)
    if user is None:
        logger.info("Admin login failed for %s from %s", body.email.lower(), ip)
        admin_store.record_audit(body.email, "login_failure", "invalid credentials", ip)
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    user_id = int(user["id"])
    otp = admin_store.otp_status(user_id)

    # OTP is mandatory for every admin account. An account that has not yet
    # confirmed a code receives an enrolment challenge instead of a session.
    if not otp["enrolled"]:
        secret = admin_store.get_mfa_secret(user_id)
        if not secret:
            secret = admin_store.generate_mfa_secret()
            admin_store.set_mfa_pending(user_id, secret)
        challenge = admin_store.create_login_challenge(user_id, ip=ip)
        admin_store.record_audit(user["email"], "login_otp_enrolment", "", ip)
        uri = admin_store.otpauth_uri(str(user["email"]), secret)
        return {
            "ok": False,
            "otpEnrolmentRequired": True,
            "challenge": challenge,
            "otpauthUri": uri,
            # Inline SVG built from the URI; scanning is far less error-prone
            # than typing a base32 key. Safe: geometry only, no untrusted text.
            "qrSvg": qr.qr_svg(uri),
            "secret": secret,
            "message": "Set up your authenticator app to finish signing in.",
        }

    # Enrolled accounts still need a code in this same request before a session
    # is created; without one we hand back a challenge token.
    if not body.mfa_code:
        challenge = admin_store.create_login_challenge(user_id, ip=ip)
        admin_store.record_audit(user["email"], "login_otp_challenge", "", ip)
        return {
            "ok": False,
            "otpRequired": True,
            "challenge": challenge,
            "message": "Enter the 6-digit code from your authenticator app.",
        }

    secret = admin_store.get_mfa_secret(user_id)
    verified = bool(secret and admin_store.verify_totp(secret, body.mfa_code))
    if not verified and admin_store.consume_recovery_code(user_id, body.mfa_code):
        verified = True
        admin_store.record_audit(user["email"], "login_recovery_code", "", ip)
    if not verified:
        admin_store.record_audit(user["email"], "login_failure", "otp invalid", ip)
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    token = admin_store.create_session(
        user_id,
        ip=ip,
        user_agent=request.headers.get("user-agent"),
    )
    set_session_cookie(
        response,
        token,
        max_age_seconds=settings.admin_session_hours * 3600,
        secure=_cookie_secure(request),
    )
    admin_store.record_audit(user["email"], "login_success", "", ip)
    logger.info("Admin login succeeded for user id=%s", user_id)
    return {"ok": True, "user": user}


async def _authenticate(email: str, password: str) -> dict[str, object] | None:
    # scrypt is intentionally CPU-heavy; keep it off the event loop.
    import asyncio

    return await asyncio.to_thread(admin_store.authenticate, email, password)


@router.post("/admin/logout")
async def admin_logout(request: Request, response: Response):
    _check_origin(request)
    user = admin_store.get_session_user(session_token(request))
    admin_store.delete_session(session_token(request))
    clear_session_cookie(response)
    if user:
        admin_store.record_audit(user["email"], "logout", "", client_ip(request))
    return {"ok": True}


@router.get("/admin/me")
async def admin_me(request: Request):
    return {"user": current_admin(request)}


# --- Traffic -----------------------------------------------------------------


@router.get("/admin/traffic")
async def admin_traffic(request: Request, days: int = 30):
    user = current_admin(request)
    require_mfa(user)
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")
    return await _load_traffic(days)


async def _load_traffic(days: int) -> dict[str, object]:
    import asyncio

    return await asyncio.to_thread(analytics_store.get_traffic_overview, days)


@router.get("/admin/traffic/export")
async def admin_traffic_export(request: Request, days: int = 30):
    """CSV with per-day views and top pages, for offline reporting."""
    user = current_admin(request)
    require_mfa(user)
    if days < 1 or days > 365:
        raise HTTPException(status_code=400, detail="days must be between 1 and 365")

    overview = await _load_traffic(days)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["Operation Child Shield traffic export"])
    writer.writerow(["window_days", days])
    writer.writerow(["since", overview["since"]])
    writer.writerow(["generated_at", overview["generatedAt"]])
    writer.writerow(["page_views", overview["pageViews"]])
    writer.writerow([])
    writer.writerow(["Daily views"])
    writer.writerow(["date", "views"])
    for point in overview["daily"]:  # type: ignore[union-attr]
        writer.writerow([point["date"], point["views"]])
    writer.writerow([])
    writer.writerow(["Top pages"])
    writer.writerow(["path", "views"])
    for page in overview["topPages"]:  # type: ignore[union-attr]
        writer.writerow([page["path"], page["views"]])

    admin_store.record_audit(
        _audit_actor(user),
        "traffic_export",
        f"days={days}",
        client_ip(request),
    )
    filename = f"ocs-traffic-{days}d.csv"
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )


# --- Health ------------------------------------------------------------------


def _db_bytes(path: Path) -> int:
    try:
        return int(path.stat().st_size)
    except OSError:
        return 0


def _analytics_health(cache_dir: Path) -> dict[str, object]:
    db = cache_dir / "analytics.db"
    rows = 0
    oldest = None
    if db.exists():
        try:
            conn = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
            try:
                rows = int(conn.execute("SELECT COUNT(*) FROM page_views").fetchone()[0])
                oldest = conn.execute("SELECT MIN(viewed_at) FROM page_views").fetchone()[0]
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            logger.warning("Could not read analytics database health", exc_info=True)
    return {"pageViewRows": rows, "oldestPageView": oldest}


@router.get("/admin/health")
async def admin_health(request: Request):
    """Small operational snapshot for the dashboard's health panel."""
    current_admin(request)
    cache_dir = Path(settings.cache_dir)
    analytics = _analytics_health(cache_dir)
    cache_files = 0
    try:
        cache_files = sum(1 for entry in cache_dir.iterdir() if entry.is_file())
    except OSError:
        pass

    return {
        "analyticsDbBytes": _db_bytes(cache_dir / "analytics.db"),
        "adminDbBytes": _db_bytes(cache_dir / "admin.db"),
        "pageViewRows": analytics["pageViewRows"],
        "oldestPageView": analytics["oldestPageView"],
        "cacheFileCount": cache_files,
        "congressApiConfigured": bool(settings.congress_api_key),
        "schedulerEnabled": settings.scheduler_enabled,
        "schedulerLastRun": admin_jobs.last_run(),
        "uptimeSeconds": int(time.time() - _STARTED_AT),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }


# --- Audit -------------------------------------------------------------------


@router.get("/admin/audit")
async def admin_audit(request: Request, limit: int = 100):
    _require_owner(request)
    return {"entries": admin_store.list_audit(limit)}


# --- Account management ------------------------------------------------------


@router.get("/admin/users")
async def admin_users(request: Request):
    """Seeded account list (no hashes). Owners only."""
    _require_owner(request)
    return {"users": admin_store.list_admins()}


@router.post("/admin/users")
async def admin_create_user(body: CreateUserRequest, request: Request):
    owner = _require_owner(request)
    _check_origin(request)
    existed = admin_store.get_admin_by_email(body.email) is not None
    try:
        user = admin_store.upsert_admin(
            body.email,
            body.password,
            display_name=body.display_name,
            role=body.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    admin_store.record_audit(
        _audit_actor(owner),
        "account_updated" if existed else "account_created",
        f"{user['email']} role={user['role']}",
        client_ip(request),
    )
    return {"user": user}


def _load_user_or_404(user_id: int) -> dict[str, object]:
    user = admin_store.get_admin_by_id(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return user


@router.post("/admin/users/{user_id}/disable")
async def admin_disable_user(user_id: int, request: Request):
    owner = _require_owner(request)
    _check_origin(request)
    target = _load_user_or_404(user_id)
    if target["id"] == owner["id"]:
        raise HTTPException(status_code=400, detail="You cannot disable your own account")
    admin_store.set_admin_active(str(target["email"]), False)
    admin_store.record_audit(
        _audit_actor(owner), "account_disabled", str(target["email"]), client_ip(request)
    )
    return {"ok": True}


@router.post("/admin/users/{user_id}/enable")
async def admin_enable_user(user_id: int, request: Request):
    owner = _require_owner(request)
    _check_origin(request)
    target = _load_user_or_404(user_id)
    admin_store.set_admin_active(str(target["email"]), True)
    admin_store.record_audit(
        _audit_actor(owner), "account_enabled", str(target["email"]), client_ip(request)
    )
    return {"ok": True}


@router.post("/admin/users/{user_id}/role")
async def admin_set_role(user_id: int, body: RoleRequest, request: Request):
    owner = _require_owner(request)
    _check_origin(request)
    target = _load_user_or_404(user_id)
    admin_store.set_admin_role(str(target["email"]), body.role)
    admin_store.record_audit(
        _audit_actor(owner),
        "role_change",
        f"{target['email']} role={body.role}",
        client_ip(request),
    )
    return {"ok": True, "role": body.role}


@router.post("/admin/users/{user_id}/revoke")
async def admin_revoke_user_sessions(user_id: int, request: Request):
    owner = _require_owner(request)
    _check_origin(request)
    target = _load_user_or_404(user_id)
    removed = admin_store.revoke_all_sessions(int(target["id"]))
    admin_store.record_audit(
        _audit_actor(owner),
        "session_revocation",
        f"{target['email']} sessions={removed}",
        client_ip(request),
    )
    return {"ok": True, "revoked": removed}


class ResetPasswordRequest(BaseModel):
    new_password: str = Field(..., min_length=1, max_length=1024)

    @field_validator("new_password")
    @classmethod
    def enforce_policy(cls, value: str) -> str:
        try:
            return passwords.validate_password(value)
        except passwords.PasswordPolicyError as exc:
            raise ValueError(str(exc)) from exc


@router.post("/admin/users/{user_id}/reset-password")
async def admin_reset_user_password(
    user_id: int, body: ResetPasswordRequest, request: Request
):
    """Set a new password on another account and revoke its sessions.

    The password is never returned and is not emailed, so the owner relays it
    out of band. OTP state is left alone; the user keeps their authenticator.
    """
    owner = _require_owner(request)
    _check_origin(request)
    target = _load_user_or_404(user_id)

    try:
        changed = admin_store.set_admin_password(int(target["id"]), body.new_password)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not changed:
        raise HTTPException(status_code=404, detail="Account not found")

    revoked = admin_store.revoke_all_sessions(int(target["id"]))
    admin_store.record_audit(
        _audit_actor(owner),
        "password_reset",
        f"{target['email']} sessions_revoked={revoked}",
        client_ip(request),
    )
    return {"ok": True, "sessionsRevoked": revoked}


@router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: int, request: Request):
    """Permanently delete an account.

    Refuses to remove the caller's own account or the last remaining owner:
    either would lock everyone out of the admin section.
    """
    owner = _require_owner(request)
    _check_origin(request)
    target = _load_user_or_404(user_id)

    if int(target["id"]) == int(owner["id"]):
        raise HTTPException(status_code=400, detail="You cannot delete your own account")
    if str(target.get("role")) == "owner" and admin_store.count_owners(
        exclude_user_id=int(target["id"])
    ) == 0:
        raise HTTPException(
            status_code=400,
            detail="This is the last owner. Promote another account first.",
        )

    # Capture the identity before the row disappears, for the audit trail.
    actor = _audit_actor(owner)
    email = str(target["email"])
    if not admin_store.delete_admin(int(target["id"])):
        raise HTTPException(status_code=404, detail="Account not found")
    admin_store.record_audit(actor, "account_deleted", email, client_ip(request))
    return {"ok": True}


# --- Self-service ------------------------------------------------------------


@router.post("/admin/password")
async def admin_change_password(body: PasswordChangeRequest, request: Request):
    user = current_admin(request)
    _check_origin(request)
    user_id = int(user["id"])
    if not await _verify_current_password(user_id, body.current_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    admin_store.set_admin_password(user_id, body.new_password)
    revoked = admin_store.revoke_all_sessions(user_id, keep_token=session_token(request))
    admin_store.record_audit(
        _audit_actor(user),
        "password_reset",
        f"sessions_revoked={revoked}",
        client_ip(request),
    )
    return {"ok": True, "revokedSessions": revoked}


async def _verify_current_password(user_id: int, password: str) -> bool:
    import asyncio

    return await asyncio.to_thread(admin_store.verify_user_password, user_id, password)


@router.get("/admin/sessions")
async def admin_sessions(request: Request):
    user = current_admin(request)
    sessions = admin_store.list_sessions(
        int(user["id"]), current_token=session_token(request)
    )
    return {"sessions": sessions}


@router.post("/admin/sessions/revoke-all")
async def admin_revoke_all_sessions(request: Request):
    user = current_admin(request)
    _check_origin(request)
    revoked = admin_store.revoke_all_sessions(int(user["id"]))
    admin_store.record_audit(
        _audit_actor(user),
        "session_revocation",
        f"self sessions={revoked}",
        client_ip(request),
    )
    return {"ok": True, "revoked": revoked}


@router.post("/admin/mfa/setup")
async def admin_mfa_setup(request: Request):
    user = current_admin(request)
    _check_origin(request)
    secret = admin_store.generate_mfa_secret()
    admin_store.set_mfa_pending(int(user["id"]), secret)
    return {
        "secret": secret,
        "otpauthUri": admin_store.otpauth_uri(str(user["email"]), secret),
    }


@router.post("/admin/mfa/enable")
async def admin_mfa_enable(body: MFAVerifyRequest, request: Request):
    user = current_admin(request)
    _check_origin(request)
    if not admin_store.enable_mfa(int(user["id"]), body.code):
        raise HTTPException(status_code=400, detail="Invalid MFA code")
    admin_store.record_audit(
        _audit_actor(user), "mfa_enabled", "", client_ip(request)
    )
    return {"ok": True, "mfaEnabled": True}


@router.post("/admin/mfa/disable")
async def admin_mfa_disable(request: Request):
    """Permanent refusal.

    The route is kept so old clients get a clear error instead of a 404, but it
    never changes state: OTP is hardcoded on for every account. Tests assert the
    account is unaffected after calling this.
    """
    current_admin(request)
    raise HTTPException(
        status_code=403,
        detail=(
            "OTP cannot be disabled. It is required for every admin account, "
            "for you and for everyone else."
        ),
    )


class OtpVerifyRequest(BaseModel):
    challenge: str = Field(..., min_length=10, max_length=256)
    code: str = Field(..., min_length=6, max_length=16)

    @field_validator("challenge", "code")
    @classmethod
    def strip(cls, value: str) -> str:
        return (value or "").strip()


@router.post("/admin/otp/verify")
async def admin_otp_verify(
    body: OtpVerifyRequest, request: Request, response: Response
):
    """Second login step: exchange a challenge plus OTP for a session.

    Also handles first-time enrolment: the same challenge created at password
    verification works here, and the first valid code enrols the account.
    """
    ip = client_ip(request)
    rate_limit(
        ip,
        bucket="admin_otp",
        max_hits=15,
        window_seconds=300.0,
        detail="Too many verification attempts. Try again in a few minutes.",
    )
    _check_origin(request)

    challenge = admin_store.peek_login_challenge(body.challenge)
    if challenge is None:
        raise HTTPException(
            status_code=401,
            detail="This sign-in attempt expired. Enter your password again.",
        )
    if challenge["attempts"] >= admin_store.MAX_CHALLENGE_ATTEMPTS:
        raise HTTPException(
            status_code=401,
            detail="Too many incorrect codes. Enter your password again.",
        )

    user_id = int(challenge["userId"])
    user = admin_store.get_admin_by_id(user_id)
    if user is None or not user.get("isActive"):
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    code = body.code.strip().replace(" ", "")
    otp = admin_store.otp_status(user_id)
    verified = False
    enrolment_codes: list[str] | None = None

    if not otp["enrolled"]:
        # First valid code both enrols the account and yields recovery codes.
        enrolment_codes = admin_store.confirm_otp_enrolment(user_id, code)
        if enrolment_codes is None:
            admin_store.bump_challenge_attempts(body.challenge)
            admin_store.record_audit(
                str(user["email"]), "login_failure", "otp enrolment code invalid", ip
            )
            raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)
        admin_store.record_audit(str(user["email"]), "otp_enrolled", "", ip)
        verified = True
    else:
        secret = admin_store.get_mfa_secret(user_id)
        if secret and admin_store.verify_totp(secret, code):
            verified = True
        elif admin_store.consume_recovery_code(user_id, code):
            verified = True
            admin_store.record_audit(str(user["email"]), "login_recovery_code", "", ip)

    if not verified:
        attempts = admin_store.bump_challenge_attempts(body.challenge)
        admin_store.record_audit(str(user["email"]), "login_failure", "otp invalid", ip)
        logger.info("Admin OTP failure for user id=%s (attempt %s)", user_id, attempts)
        raise HTTPException(status_code=401, detail=GENERIC_LOGIN_ERROR)

    admin_store.consume_login_challenge(body.challenge)
    token = admin_store.create_session(
        user_id, ip=ip, user_agent=request.headers.get("user-agent")
    )
    set_session_cookie(
        response,
        token,
        max_age_seconds=settings.admin_session_hours * 3600,
        secure=_cookie_secure(request),
    )
    admin_store.record_audit(str(user["email"]), "login_success", "otp", ip)
    return {
        "ok": True,
        "user": user,
        "recoveryCodes": enrolment_codes,
    }





# --- Backups -----------------------------------------------------------------


@router.post("/admin/backup")
async def admin_run_backup(request: Request):
    owner = _require_owner(request)
    _check_origin(request)
    import asyncio

    try:
        name = await asyncio.to_thread(backup.create_backup)
    except (OSError, sqlite3.Error) as exc:
        logger.exception("Admin backup failed")
        raise HTTPException(status_code=500, detail="Backup failed") from exc
    admin_store.record_audit(
        _audit_actor(owner), "backup_created", name, client_ip(request)
    )
    return {"ok": True, "filename": name}


@router.get("/admin/applications")
async def admin_list_applications(request: Request, limit: int = 200):
    """Board applications, newest first.

    Values are sanitized before storage and again on read; the UI renders them
    as text. Owners and editors may read them (viewers may not).
    """
    require_role(request, "owner", "editor")
    if limit < 1 or limit > 500:
        raise HTTPException(status_code=400, detail="limit must be between 1 and 500")
    import asyncio

    rows = await asyncio.to_thread(
        applications_store.list_applications_with_ids, limit
    )
    return {"applications": rows, "total": len(rows)}


@router.get("/admin/applications/export")
async def admin_export_applications(request: Request):
    """CSV download. Owner and editor only; audited because it leaves the system."""
    actor = require_role(request, "owner", "editor")
    import asyncio
    import io

    from fastapi.responses import StreamingResponse

    payload = await asyncio.to_thread(applications_store.export_applications_csv)
    admin_store.record_audit(
        _audit_actor(actor), "applications_exported", "", client_ip(request)
    )
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return StreamingResponse(
        io.StringIO(payload),
        media_type="text/csv",
        headers={
            "Content-Disposition": (
                f'attachment; filename="board-applications-{stamp}.csv"'
            )
        },
    )


@router.delete("/admin/applications/{application_id}")
async def admin_delete_application(application_id: str, request: Request):
    """Delete one application. Destructive, so owners only, and audited."""
    owner = _require_owner(request)
    _check_origin(request)
    if not re.fullmatch(r"[0-9a-f]{16,32}", application_id or ""):
        raise HTTPException(status_code=400, detail="Invalid application id")
    import asyncio

    removed = await asyncio.to_thread(
        applications_store.delete_application, application_id
    )
    if not removed:
        raise HTTPException(status_code=404, detail="Application not found")
    admin_store.record_audit(
        _audit_actor(owner),
        "application_deleted",
        application_id,
        client_ip(request),
    )
    return {"ok": True}


@router.get("/admin/backups")
async def admin_list_backups(request: Request):
    owner = _require_owner(request)
    import asyncio

    return {"backups": await asyncio.to_thread(backup.list_backups)}
