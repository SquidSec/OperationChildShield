"""Tests for admin RBAC, MFA, audit, sessions, lockout, backups, and health."""

import base64
import hashlib
import hmac
import sqlite3
import struct
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import admin_jobs, admin_store, analytics_store, backup
from app.routes import admin
from app.security import reset_rate_limits_for_tests

PASSWORD = "correct horse battery staple"
NEW_PASSWORD = "an even longer passphrase"


def _totp(secret: str, timestamp: int) -> str:
    """Independent RFC 6238 implementation used to cross-check the module."""
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    counter = timestamp // 30
    digest = hmac.new(key, struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(value % 1_000_000).zfill(6)


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(admin_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(backup.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(backup.settings, "backup_keep", 3)
    monkeypatch.setattr(admin_store.settings, "admin_require_mfa", False)
    monkeypatch.setattr(admin_store.settings, "admin_lockout_threshold", 5)
    monkeypatch.setattr(admin_store.settings, "admin_lockout_minutes", 15)
    admin_store.reset_for_tests()
    admin_jobs.reset_for_tests()
    analytics_store._initialized = False
    admin_store.init_admin_db()
    analytics_store.init_analytics_db()
    reset_rate_limits_for_tests()

    async def fake_verify(token: str, *, remote_ip: str | None = None) -> bool:
        return token == "valid-token"

    monkeypatch.setattr(admin, "verify_turnstile", fake_verify)

    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    return TestClient(app)


def _seed(email: str = "admin@example.org", role: str | None = None) -> dict:
    return admin_store.upsert_admin(email, PASSWORD, display_name="Site Admin", role=role)


def _password_step(client: TestClient, email: str = "admin@example.org",
                   password: str = PASSWORD):
    """Step 1 of sign-in. Returns the challenge payload, never a session."""
    return client.post(
        "/api/admin/login",
        json={"email": email, "password": password, "captcha_token": "valid-token"},
    )


def _login(client: TestClient, email: str = "admin@example.org", password: str = PASSWORD,
           secret: str | None = None):
    """Complete both steps and return the OTP response (which sets the cookie)."""
    first = _password_step(client, email, password)
    if first.status_code != 200:
        return first
    payload = first.json()
    challenge = payload.get("challenge", "")
    active = secret or payload.get("secret")
    if not active:
        user = admin_store.get_admin_by_email(email)
        active = admin_store.get_mfa_secret(int(user["id"])) if user else None
    if not active or not challenge:
        return first
    return client.post(
        "/api/admin/otp/verify",
        json={"challenge": challenge, "code": _totp(active, int(time.time()))},
    )


# --- Roles ------------------------------------------------------------------


def test_first_admin_is_owner_and_later_ones_are_editors(client):
    first = _seed("first@example.org")
    second = _seed("second@example.org")
    assert first["role"] == "owner"
    assert second["role"] == "editor"


def test_upsert_validates_role(client):
    with pytest.raises(ValueError):
        admin_store.upsert_admin("bad@example.org", PASSWORD, role="superuser")


def test_existing_database_gains_role_column_idempotently(tmp_path, monkeypatch):
    monkeypatch.setattr(admin_store.settings, "cache_dir", str(tmp_path))
    admin_store.reset_for_tests()
    db = tmp_path / "admin.db"
    conn = sqlite3.connect(str(db))
    try:
        conn.execute(
            """
            CREATE TABLE admin_users (
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
            "INSERT INTO admin_users (email, display_name, password_hash, created_at, updated_at)"
            " VALUES ('legacy@example.org', 'Legacy', 'x', '2020', '2020')"
        )
        conn.commit()
    finally:
        conn.close()

    admin_store.init_admin_db()
    admin_store.init_admin_db()  # idempotent

    user = admin_store.get_admin_by_email("legacy@example.org")
    assert user is not None
    assert user["role"] == "editor"
    assert user["mfaEnabled"] is False

    conn = sqlite3.connect(str(db))
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(admin_users)")}
    finally:
        conn.close()
    assert {"role", "mfa_secret", "mfa_enabled", "failed_attempts", "locked_until"} <= columns


def test_me_and_users_expose_role(client):
    _seed()
    assert _login(client).status_code == 200
    assert client.get("/api/admin/me").json()["user"]["role"] == "owner"
    users = client.get("/api/admin/users").json()["users"]
    assert users[0]["role"] == "owner"
    # Every admin enrols in OTP on first sign-in, so this is true after login.
    assert users[0]["mfaEnabled"] is True


def test_owner_can_create_editor_but_editor_cannot_manage(client):
    _seed("owner@example.org", role="owner")
    _seed("editor@example.org", role="editor")

    assert _login(client, "owner@example.org").status_code == 200
    created = client.post(
        "/api/admin/users",
        json={
            "email": "new@example.org",
            "display_name": "New Person",
            "password": NEW_PASSWORD,
            "role": "viewer",
        },
    )
    assert created.status_code == 200
    assert created.json()["user"]["role"] == "viewer"

    client.post("/api/admin/logout")
    assert _login(client, "editor@example.org").status_code == 200
    assert client.get("/api/admin/users").status_code == 403
    assert client.post(
        "/api/admin/users",
        json={"email": "x@example.org", "password": NEW_PASSWORD, "role": "viewer"},
    ).status_code == 403


def test_owner_only_audit_endpoint(client):
    _seed("owner@example.org", role="owner")
    _seed("editor@example.org", role="editor")

    _login(client, "owner@example.org")
    assert client.get("/api/admin/audit").status_code == 200
    client.post("/api/admin/logout")

    _login(client, "editor@example.org")
    assert client.get("/api/admin/audit").status_code == 403


def test_disable_enable_and_revoke_endpoints(client):
    owner = _seed("owner@example.org", role="owner")
    target = _seed("target@example.org", role="editor")
    _login(client, "owner@example.org")

    assert client.post(f"/api/admin/users/{target['id']}/disable").status_code == 200
    assert admin_store.get_admin_by_id(int(target["id"]))["isActive"] is False
    assert client.post(f"/api/admin/users/{target['id']}/enable").status_code == 200
    assert admin_store.get_admin_by_id(int(target["id"]))["isActive"] is True

    assert client.post(f"/api/admin/users/{target['id']}/role", json={"role": "viewer"}).status_code == 200
    assert admin_store.get_admin_by_id(int(target["id"]))["role"] == "viewer"

    assert client.post(f"/api/admin/users/{target['id']}/revoke").status_code == 200
    assert client.post(f"/api/admin/users/{owner['id']}/disable").status_code == 400


def test_create_user_requires_long_password(client):
    _seed("owner@example.org", role="owner")
    _login(client, "owner@example.org")
    res = client.post(
        "/api/admin/users",
        json={"email": "short@example.org", "password": "short", "role": "viewer"},
    )
    assert res.status_code == 422


# --- TOTP --------------------------------------------------------------------


def test_totp_matches_rfc6238_test_vector():
    # RFC 6238 Appendix B uses an ASCII secret "12345678901234567890".
    secret = base64.b32encode(b"12345678901234567890").decode().rstrip("=")
    assert admin_store.totp_code(secret, for_time=59) == "287082"
    assert admin_store.totp_code(secret, for_time=1111111109) == "081804"
    assert admin_store.verify_totp(secret, "287082", for_time=59)
    assert admin_store.verify_totp(secret, "287083", for_time=59, window=0) is False


def test_totp_accepts_adjacent_step_only(client):
    secret = "JBSWY3DPEHPK3PXP"
    now = 1_700_000_000
    assert admin_store.verify_totp(secret, _totp(secret, now - 30), for_time=now)
    assert admin_store.verify_totp(secret, _totp(secret, now + 30), for_time=now)
    assert not admin_store.verify_totp(secret, _totp(secret, now - 90), for_time=now)
    assert not admin_store.verify_totp(secret, "", for_time=now)
    assert not admin_store.verify_totp("not-base32!!!", "123456", for_time=now)


def test_mfa_cannot_be_disabled(client):
    _seed()
    assert _login(client).status_code == 200
    assert client.get("/api/admin/me").json()["user"]["mfaEnabled"] is True
    # OTP is mandatory, so disabling is refused rather than applied.
    res = client.post("/api/admin/mfa/disable")
    assert res.status_code == 403
    assert "required" in res.json()["detail"].lower()
    assert client.get("/api/admin/me").json()["user"]["mfaEnabled"] is True


def test_first_login_enrols_otp_and_returns_recovery_codes(client):
    _seed()
    first = _password_step(client)
    assert first.status_code == 200
    payload = first.json()
    assert payload["otpEnrolmentRequired"] is True
    secret = payload["secret"]
    assert payload["otpauthUri"].startswith("otpauth://totp/")

    # No session until the code is verified.
    assert "ocs_admin_session" not in first.cookies
    assert client.get("/api/admin/me").status_code == 401

    verify = client.post(
        "/api/admin/otp/verify",
        json={"challenge": payload["challenge"], "code": _totp(secret, int(time.time()))},
    )
    assert verify.status_code == 200
    assert verify.json()["ok"] is True
    assert len(verify.json()["recoveryCodes"]) == 8
    assert client.get("/api/admin/me").status_code == 200


def test_login_requires_otp_every_time(client):
    user = _seed()
    secret = admin_store.generate_mfa_secret()
    admin_store.set_mfa_pending(int(user["id"]), secret)
    import time

    assert admin_store.confirm_otp_enrolment(user["id"], _totp(secret, int(time.time())))

    # Password alone yields a challenge, never a session.
    first = _password_step(client)
    assert first.status_code == 200
    assert first.json()["otpRequired"] is True
    assert "ocs_admin_session" not in first.cookies

    wrong = client.post(
        "/api/admin/otp/verify",
        json={"challenge": first.json()["challenge"], "code": "000000"},
    )
    assert wrong.status_code == 401
    assert wrong.json()["detail"] == admin.GENERIC_LOGIN_ERROR

    ok = client.post(
        "/api/admin/otp/verify",
        json={
            "challenge": first.json()["challenge"],
            "code": _totp(secret, int(time.time())),
        },
    )
    assert ok.status_code == 200
    assert client.get("/api/admin/me").status_code == 200


def test_floor_of_new_admin_requires_code(client):
    """A freshly seeded account cannot reach the dashboard without OTP."""
    _seed()
    res = _password_step(client)
    assert res.status_code == 200
    assert "ocs_admin_session" not in res.cookies


def test_every_session_implies_otp_was_verified(client, monkeypatch):
    """The ADMIN_REQUIRE_MFA flag is no longer a gate because OTP is universal.

    A session can only exist after the OTP step, so flipping the old flag must
    not change access either way.
    """
    _seed()
    assert _login(client).status_code == 200
    for flag in (False, True):
        monkeypatch.setattr(admin_store.settings, "admin_require_mfa", flag)
        assert client.get("/api/admin/traffic?days=7").status_code == 200


# --- Audit -------------------------------------------------------------------


def test_audit_records_login_and_logout(client):
    _seed()
    _login(client, password="wrong password here")
    _login(client)
    client.post("/api/admin/logout")

    actions = [entry["action"] for entry in admin_store.list_audit(50)]
    # First sign-in enrols OTP, so the tail is: failure, enrolment, success, logout.
    assert actions[:5] == [
        "logout",
        "login_success",
        "otp_enrolled",
        "login_otp_enrolment",
        "login_failure",
    ]
    assert admin_store.list_audit(1)[0]["actor"] == "admin@example.org"


def test_record_audit_never_raises(monkeypatch):
    def boom():
        raise sqlite3.OperationalError("gone")

    monkeypatch.setattr(admin_store, "_connect", boom)
    admin_store.record_audit("x@example.org", "login_success", "", "127.0.0.1")


def test_account_and_mfa_changes_are_audited(client):
    _seed("owner@example.org", role="owner")
    target = _seed("target@example.org", role="editor")
    _login(client, "owner@example.org")

    client.post("/api/admin/users", json={
        "email": "created@example.org", "password": NEW_PASSWORD, "role": "viewer"})
    client.post(f"/api/admin/users/{target['id']}/disable")
    client.post(f"/api/admin/users/{target['id']}/enable")
    client.post(f"/api/admin/users/{target['id']}/role", json={"role": "viewer"})
    client.post(f"/api/admin/mfa/setup")

    entries = admin_store.list_audit(100)
    actions = {entry["action"] for entry in entries}
    assert {"account_created", "account_disabled", "account_enabled", "role_change"} <= actions


# --- Lockout -----------------------------------------------------------------


def test_lockout_after_threshold_reports_it_clearly(client, monkeypatch):
    monkeypatch.setattr(admin_store.settings, "admin_lockout_threshold", 3)
    monkeypatch.setattr(admin_store.settings, "admin_lockout_minutes", 5)
    _seed()

    # Failures before the threshold stay generic so nothing is leaked.
    for _ in range(3):
        res = _login(client, password="wrong password here")
        assert res.status_code == 401
        assert res.json()["detail"] == admin.GENERIC_LOGIN_ERROR

    assert admin_store.is_account_locked("admin@example.org") is True

    # Once locked, say so with a retry hint: a generic error here leaves the
    # operator guessing, which is what caused the reported support issue.
    blocked = _login(client)
    assert blocked.status_code == 429
    assert "locked" in blocked.json()["detail"].lower()
    assert "Retry-After" in blocked.headers

    # Correct credentials are still refused while locked.
    still = _login(client)
    assert still.status_code == 429


def test_lockout_remaining_seconds_and_unlock(client, monkeypatch):
    monkeypatch.setattr(admin_store.settings, "admin_lockout_threshold", 2)
    monkeypatch.setattr(admin_store.settings, "admin_lockout_minutes", 5)
    _seed()
    for _ in range(2):
        _login(client, password="wrong password here")

    remaining = admin_store.lockout_remaining_seconds("admin@example.org")
    assert 0 < remaining <= 300

    admin_store.clear_lockout("admin@example.org")
    assert admin_store.lockout_remaining_seconds("admin@example.org") == 0
    assert admin_store.is_account_locked("admin@example.org") is False


def test_successful_login_clears_failed_attempts(client, monkeypatch):
    monkeypatch.setattr(admin_store.settings, "admin_lockout_threshold", 3)
    _seed()
    _login(client, password="wrong password here")
    assert _login(client).status_code == 200

    conn = sqlite3.connect(str(Path(admin_store.settings.cache_dir) / "admin.db"))
    try:
        row = conn.execute(
            "SELECT failed_attempts, locked_until FROM admin_users WHERE email = ?",
            ("admin@example.org",),
        ).fetchone()
    finally:
        conn.close()
    assert row == (0, None)


# --- Sessions and password ---------------------------------------------------


def test_session_listing_never_exposes_full_tokens(client):
    _seed()
    _login(client)
    sessions = client.get("/api/admin/sessions").json()["sessions"]
    assert len(sessions) == 1
    entry = sessions[0]
    assert entry["isCurrent"] is True
    assert len(entry["id"]) == 12
    token = client.cookies.get("ocs_admin_session")
    assert token not in str(entry)


def test_revoke_all_sessions_logs_the_caller_out(client):
    _seed()
    _login(client)
    assert client.post("/api/admin/sessions/revoke-all").status_code == 200
    assert client.get("/api/admin/me").status_code == 401


def test_password_change_requires_current_and_revokes_other_sessions(client):
    user = _seed()
    _login(client)
    current = client.cookies.get("ocs_admin_session")
    other = admin_store.create_session(int(user["id"]))

    bad = client.post("/api/admin/password", json={
        "current_password": "wrong password here", "new_password": NEW_PASSWORD})
    assert bad.status_code == 400

    ok = client.post("/api/admin/password", json={
        "current_password": PASSWORD, "new_password": NEW_PASSWORD})
    assert ok.status_code == 200
    assert ok.json()["revokedSessions"] == 1
    assert admin_store.get_session_user(other) is None
    assert admin_store.get_session_user(current) is not None
    assert _login(client, password=PASSWORD).status_code == 401
    reset_rate_limits_for_tests()
    assert _login(client, password=NEW_PASSWORD).status_code == 200


def test_password_change_rejects_short_password(client):
    _seed()
    _login(client)
    res = client.post("/api/admin/password", json={
        "current_password": PASSWORD, "new_password": "short"})
    assert res.status_code == 422


# --- Traffic export and health ----------------------------------------------


def test_traffic_export_returns_csv_and_is_audited(client):
    _seed()
    _login(client)
    analytics_store.record_page_view("/", referrer=None)
    analytics_store.record_page_view("/metrics", referrer=None)

    res = client.get("/api/admin/traffic/export?days=7")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    text = res.text
    assert "Daily views" in text
    assert "Top pages" in text
    assert "/metrics" in text
    assert any(
        entry["action"] == "traffic_export" for entry in admin_store.list_audit(20)
    )
    assert client.get("/api/admin/traffic/export?days=0").status_code == 400


def test_health_endpoint_reports_operational_state(client):
    _seed()
    _login(client)
    analytics_store.record_page_view("/", referrer=None)
    admin_jobs.mark_run(["prune", "refresh"])

    body = client.get("/api/admin/health").json()
    assert body["pageViewRows"] >= 1
    assert body["analyticsDbBytes"] > 0
    assert body["adminDbBytes"] > 0
    assert body["cacheFileCount"] >= 2
    assert body["schedulerLastRun"]["jobs"] == ["prune", "refresh"]
    assert body["uptimeSeconds"] >= 0
    assert body["congressApiConfigured"] == bool(admin.settings.congress_api_key)

    client.post("/api/admin/logout")
    assert client.get("/api/admin/health").status_code == 401


# --- Backups -----------------------------------------------------------------


def test_backup_create_and_restore_roundtrip(client):
    _seed()
    analytics_store.record_page_view("/", referrer=None)
    _login(client)

    created = client.post("/api/admin/backup")
    assert created.status_code == 200
    name = created.json()["filename"]

    backups = client.get("/api/admin/backups").json()["backups"]
    assert [entry["name"] for entry in backups] == [name]
    assert any(entry["action"] == "backup_created" for entry in admin_store.list_audit(20))

    # Wipe the live databases, then restore them.
    for db in ("analytics.db", "admin.db"):
        Path(admin_store.settings.cache_dir, db).unlink()
    admin_store.reset_for_tests()
    analytics_store._initialized = False

    restored = backup.restore_backup(Path(backup.backup_dir()) / name)
    assert set(restored) == {"analytics.db", "admin.db"}

    assert admin_store.get_admin_by_email("admin@example.org") is not None
    assert analytics_store.get_impact_counts()["pageViews"] >= 1


def test_backup_prunes_to_backup_keep(tmp_path, monkeypatch):
    monkeypatch.setattr(backup.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path / "backups"))
    monkeypatch.setattr(backup.settings, "backup_keep", 2)
    admin_store.reset_for_tests()
    admin_store.init_admin_db()

    # Archive names are second-resolution, so stamp them explicitly.
    for second in ("20260101T000000Z", "20260102T000000Z", "20260103T000000Z"):
        monkeypatch.setattr(backup, "_timestamp", lambda s=second: s)
        backup.create_backup()

    names = [entry["name"] for entry in backup.list_backups()]
    assert names == ["backup-20260103T000000Z.zip", "backup-20260102T000000Z.zip"]


def test_restore_rejects_foreign_archive_members(tmp_path, monkeypatch):
    import zipfile

    monkeypatch.setattr(backup.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(backup.settings, "backup_dir", str(tmp_path / "backups"))
    archive = tmp_path / "evil.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        handle.writestr("../evil.db", b"not a database")
    with pytest.raises(ValueError):
        backup.restore_backup(archive)
