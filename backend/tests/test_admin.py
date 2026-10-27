import sqlite3
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import admin_store, analytics_store, captcha
from app.routes import admin
from app.security import reset_rate_limits_for_tests
from tests.admin_login_helpers import enrol, login as full_login, totp

PASSWORD = "correct horse battery staple"


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(admin_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(admin_store.settings, "admin_captcha_disabled", False)
    monkeypatch.setattr(admin_store.settings, "turnstile_secret_key", "")
    monkeypatch.setattr(admin_store.settings, "turnstile_site_key", "")
    admin_store.reset_for_tests()
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


def _seed(password: str = PASSWORD) -> dict:
    return admin_store.upsert_admin("Admin@Example.org", password, display_name="Site Admin")


def _password_step(client: TestClient, password: str = PASSWORD, token: str = "valid-token"):
    return client.post(
        "/api/admin/login",
        json={"email": "admin@example.org", "password": password, "captcha_token": token},
    )


def _login(client: TestClient, password: str = PASSWORD, token: str = "valid-token"):
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
            "captcha_token": "valid-token",
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


def test_login_rejected_when_captcha_unconfigured(client, monkeypatch):
    _seed()
    # Fail closed: no secret and no explicit dev bypass means no logins.
    monkeypatch.setattr(
        admin,
        "verify_turnstile",
        captcha.verify_turnstile,
    )
    res = _login(client)
    assert res.status_code == 400
    assert "ocs_admin_session" not in res.cookies


def test_captcha_verification_fails_closed_when_unconfigured(monkeypatch):
    import asyncio

    monkeypatch.setattr(captcha.settings, "turnstile_secret_key", "")
    monkeypatch.setattr(captcha.settings, "admin_captcha_disabled", False)
    assert asyncio.run(captcha.verify_turnstile("token")) is False

    monkeypatch.setattr(captcha.settings, "admin_captcha_disabled", True)
    assert asyncio.run(captcha.verify_turnstile("")) is True


def test_captcha_posts_to_cloudflare_and_checks_hostname(monkeypatch):
    import asyncio

    captured: dict = {}

    class FakeResponse:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            captured["url"] = url
            captured["data"] = data
            return FakeResponse(
                {"success": True, "hostname": "operationchildshield.org"}
            )

    monkeypatch.setattr(captcha.settings, "turnstile_secret_key", "secret-key")
    monkeypatch.setattr(captcha.settings, "admin_captcha_disabled", False)
    monkeypatch.setattr(
        captcha.settings, "admin_allowed_hostnames", "operationchildshield.org"
    )
    monkeypatch.setattr(captcha.httpx, "AsyncClient", FakeClient)

    assert asyncio.run(captcha.verify_turnstile("tok", remote_ip="203.0.113.9")) is True
    assert captured["url"].startswith("https://challenges.cloudflare.com/")
    assert captured["data"]["secret"] == "secret-key"
    assert captured["data"]["response"] == "tok"
    assert captured["data"]["remoteip"] == "203.0.113.9"


def test_captcha_rejects_unexpected_hostname(monkeypatch):
    import asyncio

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"success": True, "hostname": "evil.example"}

    class FakeClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def post(self, url, data):
            return FakeResponse()

    monkeypatch.setattr(captcha.settings, "turnstile_secret_key", "secret-key")
    monkeypatch.setattr(captcha.settings, "admin_captcha_disabled", False)
    monkeypatch.setattr(
        captcha.settings, "admin_allowed_hostnames", "operationchildshield.org"
    )
    monkeypatch.setattr(captcha.httpx, "AsyncClient", FakeClient)

    assert asyncio.run(captcha.verify_turnstile("tok")) is False


def test_admin_config_reports_captcha_state(client, monkeypatch):
    res = client.get("/api/admin/config")
    assert res.status_code == 200
    assert res.json()["captchaRequired"] is False

    monkeypatch.setattr(admin_store.settings, "turnstile_site_key", "site-key")
    monkeypatch.setattr(admin_store.settings, "turnstile_secret_key", "secret-key")
    body = client.get("/api/admin/config").json()
    assert body["captchaRequired"] is True
    assert body["captchaSiteKey"] == "site-key"
    assert body["captchaConfigured"] is True
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
            "captcha_token": "valid-token",
        },
        headers={"Origin": "https://evil.example"},
    )
    assert res.status_code == 403
    assert "ocs_admin_session" not in res.cookies
