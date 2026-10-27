"""Constituent session cookies and the auth dependency.

Separate cookie name from the admin session so an admin and a constituent can be
signed in at the same time without interfering.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import HTTPException, Request

from app.config import settings
from app import users_store

logger = logging.getLogger(__name__)

USER_COOKIE_NAME = "ocs_user_session"
SESSION_DAYS = 14

_lock = threading.Lock()


def _db_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "users.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


_sessions_ready = False


def _init_sessions() -> None:
    global _sessions_ready
    if _sessions_ready:
        return
    users_store.ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    ip TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON user_sessions(expires_at)"
            )
            conn.commit()
            _sessions_ready = True
        finally:
            conn.close()


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_user_session(user_id: int, ip: str | None = None) -> str:
    import secrets

    _init_sessions()
    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM user_sessions WHERE expires_at < ?", (now.isoformat(),))
            conn.execute(
                """
                INSERT INTO user_sessions (token_hash, user_id, created_at, expires_at, ip)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _digest(token),
                    user_id,
                    now.isoformat(),
                    (now + timedelta(days=SESSION_DAYS)).isoformat(),
                    (ip or "")[:64] or None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    return token


def get_session_user(token: str) -> dict[str, object] | None:
    if not token:
        return None
    _init_sessions()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT u.* FROM user_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1
                """,
                (_digest(token), datetime.now(timezone.utc).isoformat()),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "displayName": row["display_name"],
        "emailVerified": bool(row["email_verified"]),
    }


def delete_user_session(token: str) -> None:
    if not token:
        return
    _init_sessions()
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM user_sessions WHERE token_hash = ?", (_digest(token),))
            conn.commit()
        finally:
            conn.close()


def delete_sessions_for_user(user_id: int) -> None:
    _init_sessions()
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()


def user_session_token(request: Request) -> str:
    return (request.cookies.get(USER_COOKIE_NAME) or "").strip()


def current_user(request: Request) -> dict[str, object]:
    user = get_session_user(user_session_token(request))
    if not user:
        raise HTTPException(status_code=401, detail="Sign in required")
    return user


def optional_user(request: Request) -> dict[str, object] | None:
    return get_session_user(user_session_token(request))


def set_user_cookie(response, token: str, *, max_age_seconds: int, secure: bool) -> None:
    response.set_cookie(
        key=USER_COOKIE_NAME,
        value=token,
        max_age=max_age_seconds,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def clear_user_cookie(response) -> None:
    response.delete_cookie(key=USER_COOKIE_NAME, path="/", httponly=True, samesite="lax")


def reset_for_tests() -> None:
    global _sessions_ready
    _sessions_ready = False
