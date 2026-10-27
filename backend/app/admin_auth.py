"""Admin session cookie helpers and the auth dependency."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app import admin_store

COOKIE_NAME = "ocs_admin_session"


def session_token(request: Request) -> str:
    return (request.cookies.get(COOKIE_NAME) or "").strip()


def current_admin(request: Request) -> dict[str, object]:
    user = admin_store.get_session_user(session_token(request))
    if not user:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Cookie"},
        )
    return user


def set_session_cookie(response, token: str, *, max_age_seconds: int, secure: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="strict",
        # Path "/" so the Next.js server can read the session when rendering
        # /admin and forward it to the API. The cookie is HttpOnly either way.
        path="/",
    )


def clear_session_cookie(response) -> None:
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="strict",
    )
