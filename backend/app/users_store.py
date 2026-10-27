"""Constituent accounts, saved lawmakers, and email alert subscriptions.

Separate SQLite database (users.db) from analytics and admin. Password hashes
use the same scrypt parameters as admin accounts. Email verification and
password reset use single-use tokens stored as digests.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.config import settings
from app.passwords import validate_password

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_initialized = False

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

VERIFY_TTL_HOURS = 48
RESET_TTL_HOURS = 2
MAX_SAVED_MEMBERS = 100


def _db_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "users.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _harden_db_file() -> None:
    try:
        os.chmod(_db_path(), 0o600)
    except OSError:
        pass


def init_users_db() -> None:
    global _initialized
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL DEFAULT '',
                    password_hash TEXT NOT NULL,
                    email_verified INTEGER NOT NULL DEFAULT 0,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS user_tokens (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    purpose TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    used_at TEXT,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS saved_members (
                    user_id INTEGER NOT NULL,
                    bioguide_id TEXT NOT NULL,
                    member_name TEXT NOT NULL DEFAULT '',
                    state TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    PRIMARY KEY (user_id, bioguide_id),
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    user_id INTEGER,
                    kind TEXT NOT NULL,
                    bioguide_id TEXT NOT NULL DEFAULT '',
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE (email, kind, bioguide_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS alert_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    status TEXT NOT NULL,
                    error TEXT,
                    created_at TEXT NOT NULL,
                    UNIQUE (email, kind, subject)
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_user_tokens_user ON user_tokens(user_id)")
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_alert_subs_kind ON alert_subscriptions(kind, is_active)"
            )
            conn.commit()
            _initialized = True
        finally:
            conn.close()
        _harden_db_file()


def ensure_initialized() -> None:
    if not _initialized:
        init_users_db()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> str:
    value = normalize_email(email)
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("Invalid email address")
    return value


def _hash_password(password: str, *, email: str = "") -> str:
    # Same policy as admin accounts (see app.passwords).
    if email:
        password = validate_password(password, email=email)
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=_SCRYPT_DKLEN
    )
    return f"scrypt${salt.hex()}${digest.hex()}"


def _verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, salt_hex, digest_hex = encoded.split("$", 2)
        if scheme != "scrypt":
            return False
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
    except (ValueError, AttributeError):
        return False
    actual = hashlib.scrypt(
        (password or "").encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=len(expected),
    )
    return hmac.compare_digest(actual, expected)


def _digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row_to_user(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "displayName": row["display_name"],
        "emailVerified": bool(row["email_verified"]),
        "isActive": bool(row["is_active"]),
        "createdAt": row["created_at"],
        "lastLoginAt": row["last_login_at"],
    }


def create_user(email: str, password: str, display_name: str = "") -> dict[str, object]:
    normalized = validate_email(email)
    name = (display_name or "").strip()[:120]
    password_hash = _hash_password(password, email=normalized)
    now = _now().isoformat()

    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            if conn.execute("SELECT 1 FROM users WHERE email = ?", (normalized,)).fetchone():
                raise ValueError("An account with this email already exists")
            cursor = conn.execute(
                """
                INSERT INTO users (email, display_name, password_hash, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (normalized, name, password_hash, now, now),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM users WHERE id = ?", (cursor.lastrowid,)).fetchone()
            return _row_to_user(row)
        finally:
            conn.close()


def get_user_by_email(email: str) -> dict[str, object] | None:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()


def get_user(user_id: int) -> dict[str, object] | None:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            return _row_to_user(row) if row else None
        finally:
            conn.close()


def authenticate(email: str, password: str) -> dict[str, object] | None:
    normalized = normalize_email(email)
    if not normalized or not password:
        return None

    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute("SELECT * FROM users WHERE email = ?", (normalized,)).fetchone()
        finally:
            conn.close()

    if row is None:
        _verify_password(password, _hash_password(secrets.token_hex(8)))
        return None
    if not row["is_active"] or not _verify_password(password, row["password_hash"]):
        return None

    now = _now().isoformat()
    with _lock:
        conn = _connect()
        try:
            conn.execute("UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?", (now, now, row["id"]))
            conn.commit()
        finally:
            conn.close()
    user = _row_to_user(row)
    user["lastLoginAt"] = now
    return user


def set_password(user_id: int, password: str) -> None:
    user = get_user(user_id)
    password_hash = _hash_password(password, email=str(user["email"]) if user else "")
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, _now().isoformat(), user_id),
            )
            conn.commit()
        finally:
            conn.close()


def mark_email_verified(user_id: int) -> None:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE users SET email_verified = 1, updated_at = ? WHERE id = ?",
                (_now().isoformat(), user_id),
            )
            conn.commit()
        finally:
            conn.close()


def create_token(user_id: int, purpose: str, *, ttl_hours: int) -> str:
    token = secrets.token_urlsafe(32)
    now = _now()
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO user_tokens (token_hash, user_id, purpose, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (_digest(token), user_id, purpose, now.isoformat(),
                 (now + timedelta(hours=ttl_hours)).isoformat()),
            )
            conn.commit()
        finally:
            conn.close()
    return token


def consume_token(token: str, purpose: str) -> int | None:
    """Validate and burn a single-use token; returns the user id."""
    if not token:
        return None
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM user_tokens
                WHERE token_hash = ? AND purpose = ? AND used_at IS NULL AND expires_at > ?
                """,
                (_digest(token), purpose, _now().isoformat()),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "UPDATE user_tokens SET used_at = ? WHERE token_hash = ?",
                (_now().isoformat(), row["token_hash"]),
            )
            conn.commit()
            return int(row["user_id"])
        finally:
            conn.close()


def list_saved_members(user_id: int) -> list[dict[str, str]]:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT bioguide_id, member_name, state FROM saved_members "
                "WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [
                {"bioguideId": r["bioguide_id"], "name": r["member_name"], "state": r["state"]}
                for r in rows
            ]
        finally:
            conn.close()


def save_member(user_id: int, bioguide_id: str, *, name: str = "", state: str = "") -> bool:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            count = conn.execute(
                "SELECT COUNT(*) FROM saved_members WHERE user_id = ?", (user_id,)
            ).fetchone()[0]
            existing = conn.execute(
                "SELECT 1 FROM saved_members WHERE user_id = ? AND bioguide_id = ?",
                (user_id, bioguide_id),
            ).fetchone()
            if not existing and count >= MAX_SAVED_MEMBERS:
                raise ValueError(f"You can save at most {MAX_SAVED_MEMBERS} lawmakers")
            conn.execute(
                """
                INSERT INTO saved_members (user_id, bioguide_id, member_name, state, created_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id, bioguide_id) DO UPDATE SET
                    member_name = excluded.member_name, state = excluded.state
                """,
                (user_id, bioguide_id, name[:120], state[:64], _now().isoformat()),
            )
            conn.commit()
            return True
        finally:
            conn.close()


def remove_saved_member(user_id: int, bioguide_id: str) -> bool:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                "DELETE FROM saved_members WHERE user_id = ? AND bioguide_id = ?",
                (user_id, bioguide_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


# --- Alert subscriptions ---------------------------------------------------

ALERT_KINDS = frozenset({"member_vote", "bill_floor_vote", "weekly_digest"})


def subscribe_alert(
    email: str,
    kind: str,
    *,
    bioguide_id: str = "",
    user_id: int | None = None,
) -> dict[str, object]:
    normalized = validate_email(email)
    alert_kind = (kind or "").strip().lower()
    if alert_kind not in ALERT_KINDS:
        raise ValueError("Invalid alert type")
    member = (bioguide_id or "").strip().upper()[:16]
    if alert_kind == "member_vote" and not member:
        raise ValueError("Choose a lawmaker for vote alerts")

    now = _now().isoformat()
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                INSERT INTO alert_subscriptions
                    (email, user_id, kind, bioguide_id, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(email, kind, bioguide_id) DO UPDATE SET
                    is_active = 1, updated_at = excluded.updated_at
                """,
                (normalized, user_id, alert_kind, member, now, now),
            )
            conn.commit()
        finally:
            conn.close()
    return {"email": normalized, "kind": alert_kind, "bioguideId": member}


def unsubscribe_alert(email: str, kind: str, *, bioguide_id: str = "") -> bool:
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                """
                UPDATE alert_subscriptions SET is_active = 0, updated_at = ?
                WHERE email = ? AND kind = ? AND bioguide_id = ?
                """,
                (_now().isoformat(), normalized, (kind or "").strip().lower(),
                 (bioguide_id or "").strip().upper()),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def unsubscribe_all(email: str) -> int:
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                "UPDATE alert_subscriptions SET is_active = 0, updated_at = ? WHERE email = ?",
                (_now().isoformat(), normalized),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()


def list_alert_subscriptions(email: str) -> list[dict[str, object]]:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT kind, bioguide_id, is_active FROM alert_subscriptions "
                "WHERE email = ? ORDER BY kind, bioguide_id",
                (normalize_email(email),),
            ).fetchall()
            return [
                {"kind": r["kind"], "bioguideId": r["bioguide_id"], "active": bool(r["is_active"])}
                for r in rows
            ]
        finally:
            conn.close()


def active_subscribers(kind: str) -> list[dict[str, str]]:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT email, bioguide_id FROM alert_subscriptions "
                "WHERE kind = ? AND is_active = 1",
                (kind,),
            ).fetchall()
            return [{"email": r["email"], "bioguideId": r["bioguide_id"]} for r in rows]
        finally:
            conn.close()


def record_delivery(email: str, kind: str, subject: str, status: str, error: str = "") -> bool:
    """Insert a delivery row; returns False if this email was already sent."""
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            try:
                conn.execute(
                    """
                    INSERT INTO alert_deliveries (email, kind, subject, status, error, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (normalize_email(email), kind, subject[:200], status, error[:500],
                     _now().isoformat()),
                )
            except sqlite3.IntegrityError:
                conn.rollback()
                return False
            conn.commit()
            return True
        finally:
            conn.close()


def was_delivered(email: str, kind: str, subject: str) -> bool:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT 1 FROM alert_deliveries WHERE email = ? AND kind = ? AND subject = ?",
                (normalize_email(email), kind, subject[:200]),
            ).fetchone()
            return row is not None
        finally:
            conn.close()


def user_count() -> int:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            return int(conn.execute("SELECT COUNT(*) FROM users").fetchone()[0])
        finally:
            conn.close()


def reset_for_tests() -> None:
    global _initialized
    with _lock:
        _initialized = False
