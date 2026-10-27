"""Admin accounts, sessions, MFA, and audit trail, stored separately from public analytics.

Passwords are scrypt hashes with per-user salts. Session tokens are random,
returned to the browser once, and only their SHA-256 digest is stored, so a
copy of the database cannot be replayed as a logged-in session. TOTP secrets
are stored as plain base32 because the server must read them back; the admin
database file is chmod 0600 to limit exposure.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import logging
import os
import re
import secrets
import sqlite3
import struct
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

from app.config import settings
from app.passwords import PasswordPolicyError, validate_password

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_initialized = False

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

ROLES = ("viewer", "editor", "owner")
DEFAULT_ROLE = "editor"

# scrypt cost parameters (OWASP-recommended baseline for interactive logins).
_SCRYPT_N = 2**14
_SCRYPT_R = 8
_SCRYPT_P = 1
_SCRYPT_DKLEN = 32

# TOTP parameters (RFC 6238 defaults).
TOTP_DIGITS = 6
TOTP_PERIOD = 30
TOTP_ISSUER = "Operation Child Shield"

# Columns added after the first release. Each entry is applied only when
# PRAGMA table_info does not list it, so existing databases migrate in place.
_USER_COLUMNS: dict[str, str] = {
    "role": f"TEXT NOT NULL DEFAULT '{DEFAULT_ROLE}'",
    "mfa_secret": "TEXT",
    "mfa_enabled": "INTEGER NOT NULL DEFAULT 0",
    "failed_attempts": "INTEGER NOT NULL DEFAULT 0",
    "locked_until": "TEXT",
    # OTP is mandatory for every admin. These track whether the account has
    # confirmed a code yet and how many recovery codes remain unused.
    "otp_confirmed_at": "TEXT",
    "recovery_codes_hash": "TEXT",
}


def _db_path() -> Path:
    base = Path(settings.cache_dir)
    base.mkdir(parents=True, exist_ok=True)
    return base / "admin.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _harden_db_file() -> None:
    try:
        os.chmod(_db_path(), 0o600)
    except OSError:
        pass


def _migrate_user_columns(conn: sqlite3.Connection) -> None:
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(admin_users)")}
    for name, ddl in _USER_COLUMNS.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE admin_users ADD COLUMN {name} {ddl}")


def init_admin_db() -> None:
    global _initialized
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL UNIQUE,
                    display_name TEXT NOT NULL,
                    password_hash TEXT NOT NULL,
                    is_active INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_login_at TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_sessions (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    ip TEXT,
                    user_agent TEXT,
                    FOREIGN KEY (user_id) REFERENCES admin_users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_sessions_expires ON admin_sessions(expires_at)"
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    actor_email TEXT NOT NULL,
                    action TEXT NOT NULL,
                    detail TEXT NOT NULL DEFAULT '',
                    ip TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_audit_created ON admin_audit_log(created_at DESC)"
            )
            # Short-lived handoff between "password verified" and "OTP verified".
            # A challenge is single-use and expires in a couple of minutes, so a
            # stolen password alone can never produce a session.
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS admin_login_challenges (
                    token_hash TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    ip TEXT,
                    FOREIGN KEY (user_id) REFERENCES admin_users(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_admin_challenges_expires "
                "ON admin_login_challenges(expires_at)"
            )
            _migrate_user_columns(conn)
            conn.commit()
            _initialized = True
        finally:
            conn.close()
        _harden_db_file()


def ensure_initialized() -> None:
    if not _initialized:
        init_admin_db()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return (email or "").strip().lower()


def validate_email(email: str) -> str:
    value = normalize_email(email)
    if len(value) > 254 or not _EMAIL_RE.match(value):
        raise ValueError("Invalid email address")
    return value


def validate_role(role: str) -> str:
    value = (role or "").strip().lower()
    if value not in ROLES:
        raise ValueError(f"Role must be one of: {', '.join(ROLES)}")
    return value


def _hash_password(
    password: str, *, salt: bytes | None = None, email: str = ""
) -> str:
    # Policy is enforced here too, so every write path (seed script, admin UI,
    # password reset) shares one rule set.
    if email:
        password = validate_password(password, email=email)
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=_SCRYPT_N,
        r=_SCRYPT_R,
        p=_SCRYPT_P,
        dklen=_SCRYPT_DKLEN,
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


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _row_to_user(row: sqlite3.Row) -> dict[str, object]:
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "displayName": row["display_name"],
        "isActive": bool(row["is_active"]),
        "lastLoginAt": row["last_login_at"],
        "role": (row["role"] or DEFAULT_ROLE) if _has_column(row, "role") else DEFAULT_ROLE,
        "mfaEnabled": bool(row["mfa_enabled"]) if _has_column(row, "mfa_enabled") else False,
    }


def _has_column(row: sqlite3.Row, name: str) -> bool:
    return name in row.keys()


def upsert_admin(
    email: str,
    password: str,
    *,
    display_name: str = "",
    is_active: bool = True,
    role: str | None = None,
) -> dict[str, object]:
    """Create an admin, or reset the password/name of an existing one.

    The very first account becomes an owner so a fresh install keeps a single
    account that can manage the others; later accounts default to editor.
    """
    normalized = validate_email(email)
    role_value = validate_role(role) if role is not None else None
    name = (display_name or "").strip()[:120] or normalized.split("@")[0]
    password_hash = _hash_password(password, email=normalized)
    now = _now().isoformat()

    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            existing = conn.execute(
                "SELECT id, role FROM admin_users WHERE email = ?", (normalized,)
            ).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE admin_users
                    SET display_name = ?, password_hash = ?, is_active = ?, role = ?,
                        failed_attempts = 0, locked_until = NULL, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        name,
                        password_hash,
                        1 if is_active else 0,
                        role_value or (existing["role"] or DEFAULT_ROLE),
                        now,
                        existing["id"],
                    ),
                )
                user_id = int(existing["id"])
            else:
                admin_count = int(
                    conn.execute("SELECT COUNT(*) FROM admin_users").fetchone()[0]
                )
                if role_value is None:
                    role_value = "owner" if admin_count == 0 else DEFAULT_ROLE
                cursor = conn.execute(
                    """
                    INSERT INTO admin_users
                        (email, display_name, password_hash, is_active, created_at,
                         updated_at, role)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (normalized, name, password_hash, 1 if is_active else 0, now, now, role_value),
                )
                user_id = int(cursor.lastrowid)
            conn.commit()
            row = conn.execute(
                "SELECT * FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
            return _row_to_user(row)
        finally:
            conn.close()
        _harden_db_file()


def get_admin_by_id(user_id: int) -> dict[str, object] | None:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
    return _row_to_user(row) if row else None


def get_admin_by_email(email: str) -> dict[str, object] | None:
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE email = ?", (normalized,)
            ).fetchone()
        finally:
            conn.close()
    return _row_to_user(row) if row else None


def set_admin_role(email: str, role: str) -> bool:
    value = validate_role(role)
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                "UPDATE admin_users SET role = ?, updated_at = ? WHERE email = ?",
                (value, _now().isoformat(), normalized),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def set_admin_active(email: str, active: bool) -> bool:
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                "UPDATE admin_users SET is_active = ?, updated_at = ? WHERE email = ?",
                (1 if active else 0, _now().isoformat(), normalized),
            )
            if not active:
                conn.execute(
                    """
                    DELETE FROM admin_sessions
                    WHERE user_id IN (SELECT id FROM admin_users WHERE email = ?)
                    """,
                    (normalized,),
                )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def list_admins() -> list[dict[str, object]]:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                "SELECT * FROM admin_users ORDER BY email ASC"
            ).fetchall()
            return [_row_to_user(row) for row in rows]
        finally:
            conn.close()


# --- Passwords ---------------------------------------------------------------


def verify_user_password(user_id: int, password: str) -> bool:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT password_hash FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return False
    return _verify_password(password, row["password_hash"])


def delete_admin(user_id: int) -> bool:
    """Permanently remove an account and everything tied to it.

    Sessions and login challenges cascade via foreign keys; audit rows are kept
    on purpose so the record of what happened survives the account.
    """
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM admin_sessions WHERE user_id = ?", (user_id,))
            conn.execute(
                "DELETE FROM admin_login_challenges WHERE user_id = ?", (user_id,)
            )
            cursor = conn.execute("DELETE FROM admin_users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()


def count_owners(exclude_user_id: int | None = None) -> int:
    """How many active owners remain, optionally ignoring one account.

    Used to refuse the last owner's deletion or demotion, which would otherwise
    leave the installation unmanageable.
    """
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            if exclude_user_id is None:
                row = conn.execute(
                    "SELECT COUNT(*) FROM admin_users WHERE role = 'owner' AND is_active = 1"
                ).fetchone()
            else:
                row = conn.execute(
                    "SELECT COUNT(*) FROM admin_users "
                    "WHERE role = 'owner' AND is_active = 1 AND id != ?",
                    (exclude_user_id,),
                ).fetchone()
            return int(row[0])
        finally:
            conn.close()


def set_admin_password(user_id: int, password: str) -> bool:
    """Replace a password hash. Raises ValueError when policy is not met."""
    user = get_admin_by_id(user_id)
    if user is None:
        return False
    password_hash = _hash_password(password, email=str(user["email"]))
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            cursor = conn.execute(
                "UPDATE admin_users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, _now().isoformat(), user_id),
            )
            conn.commit()
            return cursor.rowcount > 0
        finally:
            conn.close()
        _harden_db_file()


# --- Lockout -----------------------------------------------------------------


def _lockout_settings() -> tuple[int, int]:
    threshold = max(1, int(settings.admin_lockout_threshold))
    minutes = max(1, int(settings.admin_lockout_minutes))
    return threshold, minutes


def record_failed_login(email: str) -> None:
    """Count a bad credential and lock the account at the configured threshold.

    The caller still returns the generic login error: the lockout is a backend
    brake, not a signal we want to give an attacker.
    """
    normalized = normalize_email(email)
    threshold, minutes = _lockout_settings()
    now = _now()
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT id, failed_attempts FROM admin_users WHERE email = ?", (normalized,)
            ).fetchone()
            if row is None:
                return
            attempts = int(row["failed_attempts"] or 0) + 1
            locked_until = None
            if attempts >= threshold:
                locked_until = (now + timedelta(minutes=minutes)).isoformat()
                attempts = 0
            conn.execute(
                """
                UPDATE admin_users
                SET failed_attempts = ?, locked_until = COALESCE(?, locked_until), updated_at = ?
                WHERE id = ?
                """,
                (attempts, locked_until, now.isoformat(), row["id"]),
            )
            conn.commit()
        finally:
            conn.close()


def reset_login_failures(user_id: int) -> None:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE admin_users SET failed_attempts = 0, locked_until = NULL WHERE id = ?",
                (user_id,),
            )
            conn.commit()
        finally:
            conn.close()


def is_account_locked(email: str) -> bool:
    return lockout_remaining_seconds(email) > 0


def lockout_remaining_seconds(email: str) -> int:
    """Seconds until the account unlocks; 0 when it is not locked."""
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT locked_until FROM admin_users WHERE email = ?", (normalized,)
            ).fetchone()
        finally:
            conn.close()
    if row is None or not row["locked_until"]:
        return 0
    try:
        until = datetime.fromisoformat(str(row["locked_until"]))
    except ValueError:
        return 0
    remaining = (until - _now()).total_seconds()
    return max(0, int(remaining))


def clear_lockout(email: str) -> None:
    """Reset the failure counters so the account can sign in again."""
    normalized = normalize_email(email)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE admin_users SET failed_attempts = 0, locked_until = NULL, "
                "updated_at = ? WHERE email = ?",
                (_now().isoformat(), normalized),
            )
            conn.commit()
        finally:
            conn.close()


def authenticate(email: str, password: str) -> dict[str, object] | None:
    """Return the user on valid credentials; never reveal which part failed."""
    normalized = normalize_email(email)
    if not normalized or not password:
        return None

    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT * FROM admin_users WHERE email = ?", (normalized,)
            ).fetchone()
        finally:
            conn.close()

    # Burn comparable CPU on unknown accounts to keep timing flat.
    if row is None:
        _verify_password(password, _hash_password(secrets.token_hex(8)))
        return None
    if not row["is_active"]:
        _verify_password(password, row["password_hash"])
        return None
    locked_until = row["locked_until"] if _has_column(row, "locked_until") else None
    if locked_until and str(locked_until) > _now().isoformat():
        _verify_password(password, row["password_hash"])
        return None
    if not _verify_password(password, row["password_hash"]):
        record_failed_login(normalized)
        return None

    now = _now().isoformat()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE admin_users
                SET last_login_at = ?, updated_at = ?, failed_attempts = 0, locked_until = NULL
                WHERE id = ?
                """,
                (now, now, row["id"]),
            )
            conn.commit()
        finally:
            conn.close()

    user = _row_to_user(row)
    user["lastLoginAt"] = now
    return user


# --- TOTP (RFC 6238, SHA1, 6 digits, 30s step) -------------------------------


def generate_mfa_secret() -> str:
    """Return a new base32 secret (160 bits, no padding)."""
    return base64.b32encode(secrets.token_bytes(20)).decode("ascii").rstrip("=")


def _decode_secret(secret: str) -> bytes:
    value = (secret or "").strip().replace(" ", "").upper()
    padding = "=" * (-len(value) % 8)
    return base64.b32decode(value + padding, casefold=True)


def totp_code(secret: str, for_time: int | None = None) -> str:
    """Compute the TOTP code for a Unix timestamp (defaults to now)."""
    timestamp = int(time.time() if for_time is None else for_time)
    counter = timestamp // TOTP_PERIOD
    digest = hmac.new(
        _decode_secret(secret), struct.pack(">Q", counter), hashlib.sha1
    ).digest()
    offset = digest[-1] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**TOTP_DIGITS)).zfill(TOTP_DIGITS)


def verify_totp(secret: str, code: str, *, for_time: int | None = None, window: int = 1) -> bool:
    """Verify a code, tolerating one adjacent step of clock drift."""
    candidate = (code or "").strip().replace(" ", "")
    if len(candidate) != TOTP_DIGITS or not candidate.isdigit():
        return False
    timestamp = int(time.time() if for_time is None else for_time)
    try:
        for offset in range(-window, window + 1):
            expected = totp_code(secret, timestamp + offset * TOTP_PERIOD)
            if hmac.compare_digest(expected, candidate):
                return True
    except (ValueError, TypeError, binascii.Error):
        return False
    return False


def otpauth_uri(email: str, secret: str) -> str:
    label = quote(f"{TOTP_ISSUER}:{normalize_email(email)}")
    issuer = quote(TOTP_ISSUER)
    return (
        f"otpauth://totp/{label}?secret={secret}&issuer={issuer}"
        f"&algorithm=SHA1&digits={TOTP_DIGITS}&period={TOTP_PERIOD}"
    )


def get_mfa_secret(user_id: int) -> str | None:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT mfa_secret FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
        finally:
            conn.close()
    return row["mfa_secret"] if row else None


def set_mfa_pending(user_id: int, secret: str) -> None:
    """Store a secret without turning MFA on; enable_mfa confirms it."""
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE admin_users SET mfa_secret = ?, mfa_enabled = 0, updated_at = ? WHERE id = ?",
                (secret, _now().isoformat(), user_id),
            )
            conn.commit()
        finally:
            conn.close()
        _harden_db_file()


def enable_mfa(user_id: int, code: str) -> bool:
    secret = get_mfa_secret(user_id)
    if not secret or not verify_totp(secret, code):
        return False
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE admin_users SET mfa_enabled = 1, updated_at = ? WHERE id = ?",
                (_now().isoformat(), user_id),
            )
            conn.commit()
        finally:
            conn.close()
    return True


# There is deliberately no disable_mfa(). OTP is a permanent, hardcoded
# requirement: no account, no role, and no setting can turn it off. Removing the
# function is the control; a caller cannot re-enable what does not exist.


# --- Sessions ----------------------------------------------------------------


def create_session(
    user_id: int,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
    ttl_hours: int | None = None,
) -> str:
    ensure_initialized()
    token = secrets.token_urlsafe(32)
    now = _now()
    expires = now + timedelta(hours=ttl_hours or settings.admin_session_hours)

    with _lock:
        conn = _connect()
        try:
            conn.execute("DELETE FROM admin_sessions WHERE expires_at < ?", (now.isoformat(),))
            conn.execute(
                """
                INSERT INTO admin_sessions
                    (token_hash, user_id, created_at, expires_at, ip, user_agent)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    _token_hash(token),
                    user_id,
                    now.isoformat(),
                    expires.isoformat(),
                    (ip or "")[:64] or None,
                    (user_agent or "")[:300] or None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        _harden_db_file()
    return token


def get_session_user(token: str) -> dict[str, object] | None:
    if not token:
        return None
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT u.* FROM admin_sessions s
                JOIN admin_users u ON u.id = s.user_id
                WHERE s.token_hash = ? AND s.expires_at > ? AND u.is_active = 1
                """,
                (_token_hash(token), _now().isoformat()),
            ).fetchone()
        finally:
            conn.close()
    return _row_to_user(row) if row else None


def delete_session(token: str) -> None:
    if not token:
        return
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "DELETE FROM admin_sessions WHERE token_hash = ?", (_token_hash(token),)
            )
            conn.commit()
        finally:
            conn.close()


def delete_sessions_for_user(user_id: int) -> None:
    revoke_all_sessions(user_id)


def list_sessions(user_id: int, *, current_token: str | None = None) -> list[dict[str, object]]:
    """List live sessions for a user. Only a hash prefix is exposed as an id."""
    current_hash = _token_hash(current_token) if current_token else None
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT token_hash, created_at, expires_at, ip, user_agent
                FROM admin_sessions
                WHERE user_id = ? AND expires_at > ?
                ORDER BY created_at DESC
                """,
                (user_id, _now().isoformat()),
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "id": str(row["token_hash"])[:12],
            "createdAt": row["created_at"],
            "expiresAt": row["expires_at"],
            "ip": row["ip"],
            "userAgent": row["user_agent"],
            "isCurrent": bool(current_hash and row["token_hash"] == current_hash),
        }
        for row in rows
    ]


def revoke_all_sessions(user_id: int, *, keep_token: str | None = None) -> int:
    """Delete every session for a user; optionally spare the current token."""
    keep_hash = _token_hash(keep_token) if keep_token else None
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            if keep_hash:
                cursor = conn.execute(
                    "DELETE FROM admin_sessions WHERE user_id = ? AND token_hash != ?",
                    (user_id, keep_hash),
                )
            else:
                cursor = conn.execute(
                    "DELETE FROM admin_sessions WHERE user_id = ?", (user_id,)
                )
            conn.commit()
            return int(cursor.rowcount or 0)
        finally:
            conn.close()


# --- Audit log ---------------------------------------------------------------


def record_audit(
    actor: str,
    action: str,
    detail: str = "",
    ip: str | None = None,
) -> None:
    """Append an audit row. Never raises: auditing must not break a request."""
    try:
        ensure_initialized()
        with _lock:
            conn = _connect()
            try:
                conn.execute(
                    """
                    INSERT INTO admin_audit_log (actor_email, action, detail, ip, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        (actor or "unknown")[:254],
                        (action or "unknown")[:80],
                        (detail or "")[:500],
                        (ip or "")[:64] or None,
                        _now().isoformat(),
                    ),
                )
                conn.commit()
            finally:
                conn.close()
    except Exception:  # noqa: BLE001 - best-effort audit trail
        logger.warning("Could not record admin audit event %s", action, exc_info=True)


def list_audit(limit: int = 100) -> list[dict[str, object]]:
    limit = max(1, min(int(limit or 100), 500))
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            rows = conn.execute(
                """
                SELECT id, actor_email, action, detail, ip, created_at
                FROM admin_audit_log
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        finally:
            conn.close()
    return [
        {
            "id": int(row["id"]),
            "actor": row["actor_email"],
            "action": row["action"],
            "detail": row["detail"],
            "ip": row["ip"],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


# --- Mandatory OTP login challenges -----------------------------------------

CHALLENGE_TTL_SECONDS = 300
MAX_CHALLENGE_ATTEMPTS = 5


def create_login_challenge(user_id: int, *, ip: str | None = None) -> str:
    """Issue a single-use token after the password checks out.

    The caller must still verify an OTP. Returns the raw token, which is only
    ever held by the browser for the duration of the login form.
    """
    ensure_initialized()
    raw = secrets.token_urlsafe(32)
    now = _now()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "DELETE FROM admin_login_challenges WHERE expires_at < ?",
                (now.isoformat(),),
            )
            conn.execute(
                """
                INSERT INTO admin_login_challenges
                    (token_hash, user_id, created_at, expires_at, ip)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    _token_hash(raw),
                    user_id,
                    now.isoformat(),
                    (now + timedelta(seconds=CHALLENGE_TTL_SECONDS)).isoformat(),
                    (ip or "")[:64] or None,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        _harden_db_file()
    return raw


def peek_login_challenge(raw: str) -> dict[str, object] | None:
    """Return the challenge without consuming it (for attempt tracking)."""
    if not raw:
        return None
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM admin_login_challenges
                WHERE token_hash = ? AND expires_at > ?
                """,
                (_token_hash(raw), _now().isoformat()),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return None
    return {
        "userId": int(row["user_id"]),
        "attempts": int(row["attempts"]),
        "ip": row["ip"],
    }


def bump_challenge_attempts(raw: str) -> int:
    """Count a failed OTP entry; drop the challenge once it is exhausted."""
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE admin_login_challenges SET attempts = attempts + 1 "
                "WHERE token_hash = ?",
                (_token_hash(raw),),
            )
            row = conn.execute(
                "SELECT attempts FROM admin_login_challenges WHERE token_hash = ?",
                (_token_hash(raw),),
            ).fetchone()
            attempts = int(row["attempts"]) if row else MAX_CHALLENGE_ATTEMPTS
            if attempts >= MAX_CHALLENGE_ATTEMPTS:
                conn.execute(
                    "DELETE FROM admin_login_challenges WHERE token_hash = ?",
                    (_token_hash(raw),),
                )
            conn.commit()
            return attempts
        finally:
            conn.close()


def consume_login_challenge(raw: str) -> int | None:
    """Burn the challenge and return its user id."""
    if not raw:
        return None
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                """
                SELECT * FROM admin_login_challenges
                WHERE token_hash = ? AND expires_at > ?
                """,
                (_token_hash(raw), _now().isoformat()),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                "DELETE FROM admin_login_challenges WHERE token_hash = ?",
                (row["token_hash"],),
            )
            conn.commit()
            return int(row["user_id"])
        finally:
            conn.close()


# --- OTP enrolment and recovery codes ---------------------------------------


def otp_status(user_id: int) -> dict[str, object]:
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT mfa_secret, mfa_enabled, otp_confirmed_at, recovery_codes_hash "
                "FROM admin_users WHERE id = ?",
                (user_id,),
            ).fetchone()
        finally:
            conn.close()
    if row is None:
        return {"enrolled": False, "confirmed": False, "hasPending": False}
    has_secret = bool(row["mfa_secret"])
    confirmed = bool(row["otp_confirmed_at"])
    # Enrolment is only complete when a person confirmed a code. A secret or a
    # legacy flag alone (for example set by an old tool) does not count, so an
    # account can never be treated as enrolled without going through setup.
    return {
        "enrolled": has_secret and bool(row["mfa_enabled"]) and confirmed,
        "confirmed": confirmed,
        "hasPending": has_secret and not confirmed,
        "recoveryCodesRemaining": _count_recovery_codes(row["recovery_codes_hash"]),
    }


def _count_recovery_codes(stored: str | None) -> int:
    return len([c for c in (stored or "").split(",") if c.strip()])


def generate_recovery_codes(count: int = 8) -> list[str]:
    """Human-transcribable one-time recovery codes (e.g. 4F7K-2M9Q)."""
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous characters
    codes: list[str] = []
    for _ in range(count):
        raw = "".join(secrets.choice(alphabet) for _ in range(8))
        codes.append(f"{raw[:4]}-{raw[4:]}")
    return codes


def _hash_recovery_code(code: str) -> str:
    normalized = (code or "").strip().upper().replace(" ", "")
    return hashlib.sha256(f"ocs-recovery:{normalized}".encode("utf-8")).hexdigest()


def store_recovery_codes(user_id: int, codes: list[str]) -> None:
    joined = ",".join(_hash_recovery_code(c) for c in codes)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                "UPDATE admin_users SET recovery_codes_hash = ?, updated_at = ? WHERE id = ?",
                (joined, _now().isoformat(), user_id),
            )
            conn.commit()
        finally:
            conn.close()


def consume_recovery_code(user_id: int, code: str) -> bool:
    """Spend a recovery code. Codes work once, then are removed."""
    candidate = _hash_recovery_code(code)
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            row = conn.execute(
                "SELECT recovery_codes_hash FROM admin_users WHERE id = ?", (user_id,)
            ).fetchone()
            if row is None:
                return False
            codes = [c for c in (row["recovery_codes_hash"] or "").split(",") if c.strip()]
            if candidate not in codes:
                return False
            codes.remove(candidate)
            conn.execute(
                "UPDATE admin_users SET recovery_codes_hash = ?, updated_at = ? WHERE id = ?",
                (",".join(codes), _now().isoformat(), user_id),
            )
            conn.commit()
            return True
        finally:
            conn.close()
        _harden_db_file()


def confirm_otp_enrolment(user_id: int, code: str) -> list[str] | None:
    """Verify the first code, enable OTP, and return plaintext recovery codes.

    Returns None when the code is wrong, so a caller cannot mistake a failed
    check for success. The codes are stored hashed and are never readable again.
    """
    secret = get_mfa_secret(user_id)
    if not secret or not verify_totp(secret, code):
        return None
    codes = generate_recovery_codes()
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE admin_users
                SET mfa_enabled = 1, otp_confirmed_at = ?, recovery_codes_hash = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    _now().isoformat(),
                    ",".join(_hash_recovery_code(c) for c in codes),
                    _now().isoformat(),
                    user_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
        _harden_db_file()
    return codes


def force_otp_reset(user_id: int) -> None:
    """Force re-enrolment, never removal.

    OTP stays required (`mfa_enabled` remains 1); the existing secret and
    recovery codes are discarded so the user must set up an authenticator again
    on next sign-in. This is the only supported way to recover a lost device
    short of an owner resetting the account.
    """
    ensure_initialized()
    with _lock:
        conn = _connect()
        try:
            conn.execute(
                """
                UPDATE admin_users
                SET mfa_secret = NULL, mfa_enabled = 1, otp_confirmed_at = NULL,
                    recovery_codes_hash = NULL, updated_at = ?
                WHERE id = ?
                """,
                (_now().isoformat(), user_id),
            )
            conn.execute("DELETE FROM admin_sessions WHERE user_id = ?", (user_id,))
            conn.commit()
        finally:
            conn.close()


def reset_for_tests() -> None:
    global _initialized
    with _lock:
        _initialized = False
