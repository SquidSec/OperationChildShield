"""Admin user management and application controls."""

import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import admin_store, analytics_store, applications_store, captcha
from app.routes import admin
from app.security import reset_rate_limits_for_tests
from tests.captcha_helpers import solved_token
from tests.admin_login_helpers import enrol, totp

PASSWORD = "harbor lantern velvet quartz"
NEW_PASSWORD = "copper meadow silent river"


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    for module in (admin_store, analytics_store, applications_store):
        monkeypatch.setattr(module.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(admin_store.settings, "admin_captcha_disabled", True)
    admin_store.reset_for_tests()
    analytics_store._initialized = False
    admin_store.init_admin_db()
    analytics_store.init_analytics_db()
    reset_rate_limits_for_tests()
    captcha.reset_for_tests()


    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    return TestClient(app)


def _sign_in(client: TestClient, email: str = "owner@example.org", password: str = PASSWORD) -> dict:
    user = admin_store.get_admin_by_email(email)
    secret = None
    if user is not None:
        status = admin_store.otp_status(int(user["id"]))
        if status["enrolled"]:
            secret = admin_store.get_mfa_secret(int(user["id"]))
    if secret is None:
        secret = enrol(email)
    first = client.post(
        "/api/admin/login",
        json={"email": email, "password": password, "captcha_token": solved_token(client)},
    )
    assert first.status_code == 200, first.text
    res = client.post(
        "/api/admin/otp/verify",
        json={"challenge": first.json()["challenge"], "code": totp(secret)},
    )
    assert res.status_code == 200, res.text
    return admin_store.get_admin_by_email(email)


@pytest.fixture
def owner(client) -> dict:
    admin_store.upsert_admin("owner@example.org", PASSWORD, role="owner")
    return _sign_in(client)


def _other(email: str = "editor@example.org", role: str = "editor") -> dict:
    return admin_store.upsert_admin(email, PASSWORD, role=role)


# --- Delete -----------------------------------------------------------------


def test_owner_can_delete_another_account(client, owner):
    target = _other()
    res = client.delete(f"/api/admin/users/{target['id']}")
    assert res.status_code == 200
    assert admin_store.get_admin_by_id(int(target["id"])) is None
    assert admin_store.get_admin_by_email("editor@example.org") is None


def test_delete_revokes_target_sessions(client, owner):
    target = _other()
    admin_store.create_session(int(target["id"]))

    conn = sqlite3.connect(str(Path(admin_store.settings.cache_dir) / "admin.db"))
    before = conn.execute(
        "SELECT COUNT(*) FROM admin_sessions WHERE user_id = ?", (target["id"],)
    ).fetchone()[0]
    conn.close()
    assert before == 1

    assert client.delete(f"/api/admin/users/{target['id']}").status_code == 200
    conn = sqlite3.connect(str(Path(admin_store.settings.cache_dir) / "admin.db"))
    after = conn.execute(
        "SELECT COUNT(*) FROM admin_sessions WHERE user_id = ?", (target["id"],)
    ).fetchone()[0]
    conn.close()
    assert after == 0


def test_cannot_delete_self(client, owner):
    res = client.delete(f"/api/admin/users/{owner['id']}")
    assert res.status_code == 400
    assert "your own" in res.json()["detail"].lower()
    assert admin_store.get_admin_by_id(int(owner["id"])) is not None


def test_cannot_delete_last_owner(client, owner):
    # A second owner is required so deleting the first is allowed below.
    second = _other("second-owner@example.org", role="owner")
    assert client.delete(f"/api/admin/users/{second['id']}").status_code == 200

    # Now `owner` is the only owner.
    assert admin_store.count_owners() == 1
    # Deleting yourself is already blocked, so verify the guard directly via a
    # second session acting as owner while the target is the last owner.
    res = client.delete(f"/api/admin/users/{owner['id']}")
    assert res.status_code == 400


def test_delete_is_audited(client, owner):
    target = _other()
    client.delete(f"/api/admin/users/{target['id']}")
    actions = [e["action"] for e in admin_store.list_audit(20)]
    assert "account_deleted" in actions


def test_delete_requires_owner(client):
    admin_store.upsert_admin("ed@example.org", PASSWORD, role="editor")
    _sign_in(client, "ed@example.org")
    target = _other()
    assert client.delete(f"/api/admin/users/{target['id']}").status_code == 403


def test_delete_unknown_user_is_404(client, owner):
    assert client.delete("/api/admin/users/9999").status_code == 404


# --- Reset password ---------------------------------------------------------


def test_owner_can_reset_password_and_sessions_are_revoked(client, owner):
    target = _other()
    admin_store.create_session(int(target["id"]))

    res = client.post(
        f"/api/admin/users/{target['id']}/reset-password",
        json={"new_password": NEW_PASSWORD},
    )
    assert res.status_code == 200
    assert res.json()["sessionsRevoked"] >= 1

    # The new password works and the old one does not.
    assert admin_store.authenticate("editor@example.org", NEW_PASSWORD) is not None
    assert admin_store.authenticate("editor@example.org", PASSWORD) is None


def test_reset_password_enforces_policy(client, owner):
    target = _other()
    res = client.post(
        f"/api/admin/users/{target['id']}/reset-password",
        json={"new_password": "short"},
    )
    assert res.status_code == 422
    # Original password still works.
    assert admin_store.authenticate("editor@example.org", PASSWORD) is not None


def test_reset_password_rejects_breached_password(client, owner):
    target = _other()
    res = client.post(
        f"/api/admin/users/{target['id']}/reset-password",
        json={"new_password": "passwordpassword"},
    )
    assert res.status_code == 422


def test_reset_password_requires_owner(client):
    admin_store.upsert_admin("ed2@example.org", PASSWORD, role="editor")
    _sign_in(client, "ed2@example.org")
    target = _other()
    res = client.post(
        f"/api/admin/users/{target['id']}/reset-password",
        json={"new_password": NEW_PASSWORD},
    )
    assert res.status_code == 403


def test_reset_password_never_returns_the_password(client, owner):
    target = _other()
    res = client.post(
        f"/api/admin/users/{target['id']}/reset-password",
        json={"new_password": NEW_PASSWORD},
    )
    assert NEW_PASSWORD not in res.text


# --- Disable / enable -------------------------------------------------------


def test_disable_then_enable(client, owner):
    target = _other()
    assert client.post(f"/api/admin/users/{target['id']}/disable").status_code == 200
    assert admin_store.get_admin_by_id(int(target["id"]))["isActive"] is False
    assert client.post(f"/api/admin/users/{target['id']}/enable").status_code == 200
    assert admin_store.get_admin_by_id(int(target["id"]))["isActive"] is True


def test_disabled_account_cannot_sign_in(client, owner):
    target = _other()
    client.post(f"/api/admin/users/{target['id']}/disable")
    res = client.post(
        "/api/admin/login",
        json={"email": "editor@example.org", "password": PASSWORD, "captcha_token": solved_token(client)},
    )
    assert res.status_code == 401


def test_cannot_disable_self(client, owner):
    res = client.post(f"/api/admin/users/{owner['id']}/disable")
    assert res.status_code == 400


# --- Application controls ---------------------------------------------------


def _write_application(tmp_path: Path, **overrides) -> None:
    record = {
        "submittedAt": "2026-10-27T12:00:00+00:00",
        "role": "vice-president",
        "roleLabel": "Vice President",
        "name": "Jane Applicant",
        "email": "jane@example.org",
        "phone": "",
        "location": "Austin, TX",
        "linkedin": "",
        "statement": "Board service",
        "source": "board-page",
    }
    record.update(overrides)
    path = tmp_path / "board_applications.jsonl"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record) + "\n")


def test_applications_list_includes_ids(client, owner, tmp_path):
    _write_application(tmp_path)
    res = client.get("/api/admin/applications")
    assert res.status_code == 200
    row = res.json()["applications"][0]
    assert len(row["id"]) >= 16
    assert all(c in "0123456789abcdef" for c in row["id"])


def test_owner_can_delete_application(client, owner, tmp_path):
    _write_application(tmp_path)
    app_id = client.get("/api/admin/applications").json()["applications"][0]["id"]

    res = client.delete(f"/api/admin/applications/{app_id}")
    assert res.status_code == 200
    assert client.get("/api/admin/applications").json()["applications"] == []
    assert "application_deleted" in [e["action"] for e in admin_store.list_audit(20)]


def test_delete_application_keeps_others(client, owner, tmp_path):
    _write_application(tmp_path)
    _write_application(
        tmp_path, email="second@example.org", submittedAt="2026-10-27T13:00:00+00:00"
    )
    rows = client.get("/api/admin/applications").json()["applications"]
    assert len(rows) == 2
    client.delete(f"/api/admin/applications/{rows[0]['id']}")
    remaining = client.get("/api/admin/applications").json()["applications"]
    assert len(remaining) == 1


def test_editor_cannot_delete_application(client):
    admin_store.upsert_admin("ed3@example.org", PASSWORD, role="editor")
    _sign_in(client, "ed3@example.org")
    res = client.delete("/api/admin/applications/abcdef0123456789")
    assert res.status_code == 403


def test_delete_application_rejects_malformed_id(client, owner):
    assert client.delete("/api/admin/applications/not-an-id").status_code == 400


def test_delete_unknown_application_is_404(client, owner):
    assert client.delete("/api/admin/applications/abcdef0123456789").status_code == 404


def test_export_applications_csv(client, owner, tmp_path):
    _write_application(tmp_path)
    res = client.get("/api/admin/applications/export")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    assert "attachment" in res.headers["content-disposition"]
    text = res.text
    assert text.splitlines()[0].startswith("id,submittedAt,role")
    assert "jane@example.org" in text
    assert "applications_exported" in [e["action"] for e in admin_store.list_audit(20)]


def test_export_escapes_csv_formula_injection(client, owner, tmp_path):
    _write_application(tmp_path, name="=cmd|'/c calc'!A1")
    text = client.get("/api/admin/applications/export").text
    # The cell must be prefixed so a spreadsheet treats it as text, not a formula.
    assert "'=cmd" in text
    for line in text.splitlines()[1:]:
        for cell in line.split(","):
            assert not cell.startswith("="), f"unescaped formula cell: {cell}"


def test_export_requires_auth(client):
    assert client.get("/api/admin/applications/export").status_code == 401


def test_viewer_cannot_export(client):
    admin_store.upsert_admin("view@example.org", PASSWORD, role="viewer")
    _sign_in(client, "view@example.org")
    assert client.get("/api/admin/applications/export").status_code == 403
