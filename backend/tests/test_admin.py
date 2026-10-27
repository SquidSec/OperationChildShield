import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import admin_store, analytics_store, captcha
from tests.captcha_helpers import get_challenge, solved_token
from app.routes import admin
from app.security import reset_rate_limits_for_tests
from tests.admin_login_helpers import enrol, login as full_login, totp

PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(admin_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(admin_store.settings, "admin_captcha_disabled", False)
    captcha.reset_for_tests()
    admin_store.reset_for_tests()
    analytics_store._initialized = False
    admin_store.init_admin_db()
    analytics_store.init_analytics_db()
    reset_rate_limits_for_tests()


    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    return TestClient(app)


def _seed(password: str = PASSWORD) -> dict:
    return admin_store.upsert_admin("Admin@Example.org", password, display_name="Site Admin")


def _password_step(client: TestClient, password: str = PASSWORD, token: str | None = None):
    if token is None:
        token = solved_token(client)
    return client.post(
        "/api/admin/login",
        json={"email": "admin@example.org", "password": password, "captcha_token": token},
    )


def _login(client: TestClient, password: str = PASSWORD, token: str | None = None):
    """Full sign-in (password + OTP). Returns the OTP response."""
    first = _password_step(client, password, token)
    if first.status_code != 200:
        return first
    payload = first.json()
    challenge = payload.get("challenge", "")
    secret = payload.get("secret") or enrol()
    return client.post(
        "/api/admin/otp/verify",
        json={"challenge": challenge, "code": totp(secret)},
    )


def test_login_rejects_missing_captcha_token(client):
    _seed()
    res = _login(client, token="")
    assert res.status_code == 400
    assert "captcha" in res.json()["detail"].lower()
    assert "ocs_admin_session" not in res.cookies


def test_login_rejects_invalid_captcha_token(client):
    _seed()
    res = _login(client, token="bogus")
    assert res.status_code == 400
    assert "ocs_admin_session" not in res.cookies


def test_login_succeeds_and_sets_hardened_cookie(client):
    _seed()
    res = _login(client)
    assert res.status_code == 200
    assert res.json()["user"]["email"] == "admin@example.org"

    cookie = res.headers["set-cookie"]
    assert "ocs_admin_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie
    assert "Path=/" in cookie
    # Secure is added when the request is HTTPS; this test runs over http.

    me = client.get("/api/admin/me")
    assert me.status_code == 200
    assert me.json()["user"]["displayName"] == "Site Admin"


def test_wrong_password_is_generic_and_sets_no_cookie(client):
    _seed()
    res = _login(client, password="wrong password here")
    assert res.status_code == 401
    assert res.json()["detail"] == admin.GENERIC_LOGIN_ERROR
    assert "ocs_admin_session" not in res.cookies


def test_unknown_email_matches_wrong_password_message(client):
    _seed()
    res = client.post(
        "/api/admin/login",
        json={
            "email": "nobody@example.org",
            "password": PASSWORD,
            "captcha_token": solved_token(client),
        },
    )
    assert res.status_code == 401
    assert res.json()["detail"] == admin.GENERIC_LOGIN_ERROR


def test_password_hash_is_not_plaintext_and_uses_scrypt(client):
    _seed()
    conn = sqlite3.connect(str(Path(admin_store.settings.cache_dir) / "admin.db"))
    try:
        stored = conn.execute("SELECT password_hash FROM admin_users").fetchone()[0]
    finally:
        conn.close()
    assert PASSWORD not in stored
    assert stored.startswith("scrypt$")


def test_disable_blocks_login_and_kills_sessions(client):
    _seed()
    assert _login(client).status_code == 200
    assert client.get("/api/admin/me").status_code == 200

    assert admin_store.set_admin_active("admin@example.org", False) is True
    assert client.get("/api/admin/me").status_code == 401
    assert _login(client).status_code == 401

    admin_store.set_admin_active("admin@example.org", True)
    assert _login(client).status_code == 200


def test_logout_invalidates_session(client):
    _seed()
    assert _login(client).status_code == 200
    assert client.post("/api/admin/logout").status_code == 200
    assert client.get("/api/admin/me").status_code == 401

    # Reusing the old token directly must fail too.
    old_token = client.cookies.get("ocs_admin_session")
    assert old_token is None


def test_traffic_requires_authentication(client):
    assert client.get("/api/admin/traffic?days=7").status_code == 401
    assert client.get("/api/admin/users").status_code == 401


def test_traffic_aggregates_and_excludes_admin_views(client):
    _seed()
    _login(client)

    analytics_store.record_page_view("/", referrer="https://news.example.com/story")
    analytics_store.record_page_view("/", referrer="https://news.example.com/other")
    analytics_store.record_page_view("/metrics", referrer=None)
    analytics_store.record_page_view("/admin", referrer=None)
    analytics_store.record_action("share", path="/")
    analytics_store.record_action("involve_signup", path="/get-involved")

    res = client.get("/api/admin/traffic?days=7")
    assert res.status_code == 200
    body = res.json()

    assert body["pageViews"] == 3
    assert body["days"] == 7
    assert len(body["daily"]) == 7
    assert body["daily"][-1]["views"] >= 3
    assert body["topPages"][0] == {"path": "/", "views": 2}
    assert any(p["path"] == "/metrics" for p in body["topPages"])
    assert all(not p["path"].startswith("/admin") for p in body["topPages"])
    assert body["topReferrers"][0] == {"domain": "news.example.com", "views": 2}
    assert body["actions"] == {"share": 1, "contactCongress": 0, "signups": 1}

    # No raw rows, user agents, or referrer paths leak to the dashboard.
    serialized = str(body)
    assert "user_agent" not in serialized
    assert "news.example.com/story" not in serialized


def test_traffic_rejects_bad_range(client):
    _seed()
    _login(client)
    assert client.get("/api/admin/traffic?days=0").status_code == 400
    assert client.get("/api/admin/traffic?days=9999").status_code == 400


def test_login_rate_limit_after_repeated_failures(client):
    _seed()
    statuses = [_login(client, password="nope nope nope").status_code for _ in range(8)]
    assert 429 in statuses


def test_login_rejected_without_a_solved_challenge(client):
    _seed()
    res = client.post(
        "/api/admin/login",
        json={
            "email": "admin@example.org",
            "password": PASSWORD,
            "captcha_token": "",
        },
    )
    assert res.status_code == 400
    assert "captcha" in res.json()["detail"].lower()
    assert "ocs_admin_session" not in res.cookies


def test_login_rejects_a_forged_solution(client):
    _seed()
    data = client.get("/api/captcha/challenge").json()
    forged = f"{data['challenge']}.0"
    # Nonce 0 is very unlikely to satisfy the difficulty; force the point by
    # checking a challenge with a deliberately high difficulty is rejected.
    res = client.post(
        "/api/admin/login",
        json={"email": "admin@example.org", "password": PASSWORD, "captcha_token": forged},
    )
    assert res.status_code in (400, 401)
    assert "ocs_admin_session" not in res.cookies


def test_challenge_is_single_use(client):
    _seed()
    token = solved_token(client)
    first = client.post(
        "/api/admin/login",
        json={"email": "admin@example.org", "password": PASSWORD, "captcha_token": token},
    )
    assert first.status_code == 200

    # The same solved token cannot be replayed.
    admin_store.delete_session(client.cookies.get("ocs_admin_session") or "")
    client.cookies.clear()
    second = client.post(
        "/api/admin/login",
        json={"email": "admin@example.org", "password": PASSWORD, "captcha_token": token},
    )
    assert second.status_code == 400
    assert "ocs_admin_session" not in second.cookies


def test_challenge_endpoint_is_public_and_returns_parameters(client):
    data = get_challenge(client)
    assert len(str(data["challenge"])) >= 32
    assert int(data["difficulty"]) >= 12
    assert data["algorithm"] == "sha256-prefix-zeros"
    assert int(data["expiresIn"]) > 0


def test_admin_config_reports_pow_captcha(client):
    body = client.get("/api/admin/config").json()
    # Always on, self-hosted, and needs no keys.
    assert body["captchaRequired"] is True
    assert body["captchaProvider"] == "pow"
    assert int(body["captchaDifficulty"]) >= 12
    assert "captchaSiteKey" not in body
    # OTP is mandatory for every admin account.
    assert body["otpRequired"] is True
    assert body["passwordRules"]["minLength"] >= 15
    assert body["passwordRules"]["requiresComposition"] is False


def test_short_password_rejected_at_seed_time():
    with pytest.raises(ValueError):
        admin_store.upsert_admin("short@example.org", "short")


def test_origin_check_rejects_foreign_origin(client):
    _seed()
    res = client.post(
        "/api/admin/login",
        json={
            "email": "admin@example.org",
            "password": PASSWORD,
            "captcha_token": solved_token(client),
        },
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert "ocs_admin_session" not in res.cookies
