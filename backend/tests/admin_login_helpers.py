"""Shared helpers for admin login tests.

OTP is mandatory, so signing in is always two requests: password (which returns
a challenge) then a TOTP code. These helpers keep the individual tests focused
on the behaviour they cover instead of repeating the handshake.
"""

from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app import admin_store


def totp(secret: str, timestamp: int | None = None) -> str:
    return admin_store.totp_code(secret, int(time.time() if timestamp is None else timestamp))


def enrol(email: str = "admin@example.org") -> str:
    """Enrol an existing admin in OTP and return the secret."""
    user = admin_store.get_admin_by_email(email)
    assert user is not None, f"no admin for {email}"
    user_id = int(user["id"])
    secret = admin_store.generate_mfa_secret()
    admin_store.set_mfa_pending(user_id, secret)
    codes = admin_store.confirm_otp_enrolment(user_id, totp(secret))
    assert codes, "enrolment should return recovery codes"
    return secret


def login(
    client: TestClient,
    email: str = "admin@example.org",
    password: str = "correct horse battery staple",
    *,
    secret: str | None = None,
    captcha_token: str = "valid-token",
) -> tuple[dict, dict]:
    """Perform the two-step login.

    Returns ``(password_response, otp_response)`` so tests can assert on either
    step. The session cookie is set by the OTP response.
    """
    first = client.post(
        "/api/admin/login",
        json={"email": email, "password": password, "captcha_token": captcha_token},
    )
    payload = first.json() if first.headers.get("content-type", "").startswith("application/json") else {}
    challenge = payload.get("challenge", "")
    if first.status_code != 200 or not challenge:
        return payload, {}

    # A brand-new account gets its secret in the login response.
    active_secret = secret or payload.get("secret") or enrol(email)
    second = client.post(
        "/api/admin/otp/verify",
        json={"challenge": challenge, "code": totp(active_secret)},
    )
    body = second.json() if second.headers.get("content-type", "").startswith("application/json") else {}
    return payload, body


def login_with_session(client: TestClient, email: str = "admin@example.org") -> str:
    """Sign in fully and return the OTP secret used."""
    user = admin_store.get_admin_by_email(email)
    secret = None
    if user is not None:
        existing = admin_store.get_mfa_secret(int(user["id"]))
        status = admin_store.otp_status(int(user["id"]))
        secret = existing if status["enrolled"] else None
    if secret is None:
        secret = enrol(email)
    _, body = login(client, email, secret=secret)
    assert body.get("ok") is True, f"login failed: {body}"
    return secret
