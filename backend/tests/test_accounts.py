from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import analytics_store, users_store
from app import user_auth
from app.routes import accounts
from app.security import reset_rate_limits_for_tests


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(users_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(users_store.settings, "admin_cookie_secure", False)
    users_store.reset_for_tests()
    user_auth.reset_for_tests()
    users_store.init_users_db()
    reset_rate_limits_for_tests()

    app = FastAPI()
    app.include_router(accounts.router, prefix="/api")
    return TestClient(app)


@pytest.fixture
def sent(monkeypatch) -> list[tuple[str, str, str]]:
    """Capture outbound email instead of hitting SMTP."""
    outbox: list[tuple[str, str, str]] = []
    monkeypatch.setattr(
        accounts, "_send_verification_email", lambda to, token: outbox.append(("verify", to, token))
    )
    monkeypatch.setattr(
        accounts, "_send_reset_email", lambda to, token: outbox.append(("reset", to, token))
    )
    return outbox


def _register(client: TestClient, email="user@example.org", password="a very strong passphrase"):
    return client.post(
        "/api/account/register",
        json={"email": email, "password": password, "displayName": "Test User", "consent": True},
    )


def _token_for(email: str, purpose: str) -> str:
    """Read the raw token by issuing a fresh one (tokens are stored hashed)."""
    user = users_store.get_user_by_email(email)
    return users_store.create_token(int(user["id"]), purpose, ttl_hours=1)


def test_register_requires_consent(client, sent):
    res = client.post(
        "/api/account/register",
        json={"email": "x@example.org", "password": "a very strong passphrase", "consent": False},
    )
    assert res.status_code == 400
    assert "consent" in res.json()["detail"].lower()


def test_register_creates_unverified_user_and_sends_email(client, sent):
    res = _register(client)
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert "check your email" in res.json()["message"].lower()

    user = users_store.get_user_by_email("user@example.org")
    assert user is not None
    assert user["emailVerified"] is False
    assert any(kind == "verify" for kind, _, _ in sent)


def test_register_duplicate_does_not_reveal_existence(client, sent):
    _register(client)
    res = _register(client)
    assert res.status_code == 200
    assert res.json()["ok"] is True


def test_short_password_rejected(client, sent):
    res = _register(client, password="short")
    assert res.status_code == 400


def test_login_blocked_until_verified_then_works(client, sent):
    _register(client)
    denied = client.post(
        "/api/account/login",
        json={"email": "user@example.org", "password": "a very strong passphrase"},
    )
    assert denied.status_code == 403
    assert "confirm" in denied.json()["detail"].lower()

    token = _token_for("user@example.org", "verify_email")
    verified = client.post("/api/account/verify", json={"token": token})
    assert verified.status_code == 200
    assert "ocs_user_session" in verified.cookies

    # Verification also signs the user in.
    me = client.get("/api/account/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "user@example.org"


def test_verify_token_is_single_use(client, sent):
    _register(client)
    token = _token_for("user@example.org", "verify_email")
    assert client.post("/api/account/verify", json={"token": token}).status_code == 200
    assert client.post("/api/account/verify", json={"token": token}).status_code == 400


def test_wrong_password_is_generic(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})
    client.post("/api/account/logout")

    res = client.post(
        "/api/account/login",
        json={"email": "user@example.org", "password": "definitely not the password"},
    )
    assert res.status_code == 401
    assert res.json()["detail"] == accounts.GENERIC_AUTH_ERROR


def test_unknown_email_login_matches_wrong_password(client, sent):
    res = client.post(
        "/api/account/login", json={"email": "nobody@example.org", "password": "whatever-password"}
    )
    assert res.status_code == 401
    assert res.json()["detail"] == accounts.GENERIC_AUTH_ERROR


def test_password_reset_flow(client, sent):
    _register(client)
    res = client.post("/api/account/password/request", json={"email": "user@example.org"})
    assert res.status_code == 200
    assert any(kind == "reset" for kind, _, _ in sent)

    token = _token_for("user@example.org", "reset_password")
    reset = client.post(
        "/api/account/password/reset",
        json={"token": token, "password": "brand new passphrase nine"},
    )
    assert reset.status_code == 200

    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})
    login = client.post(
        "/api/account/login",
        json={"email": "user@example.org", "password": "brand new passphrase nine"},
    )
    assert login.status_code == 200


def test_password_reset_for_unknown_email_is_silent(client, sent):
    res = client.post("/api/account/password/request", json={"email": "ghost@example.org"})
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert not sent


def test_saved_members_roundtrip(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})

    added = client.post(
        "/api/account/saved-members",
        json={"bioguideId": "A000055", "name": "Robert Aderholt", "state": "Alabama"},
    )
    assert added.status_code == 200
    assert added.json()["members"][0]["bioguideId"] == "A000055"

    me = client.get("/api/account/me")
    assert me.json()["savedMembers"][0]["name"] == "Robert Aderholt"

    removed = client.delete("/api/account/saved-members/A000055")
    assert removed.status_code == 200
    assert removed.json()["members"] == []


def test_saved_members_requires_login(client):
    assert client.get("/api/account/saved-members").status_code == 401


def test_alerts_subscribe_and_unsubscribe(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})

    sub = client.post("/api/account/alerts", json={"kind": "weekly_digest", "bioguideId": ""})
    assert sub.status_code == 200

    alerts = client.get("/api/account/alerts")
    assert alerts.status_code == 200
    assert alerts.json()["alerts"][0]["kind"] == "weekly_digest"
    assert alerts.json()["alerts"][0]["active"] is True

    off = client.delete("/api/account/alerts/weekly_digest")
    assert off.status_code == 200
    assert off.json()["alerts"][0]["active"] is False


def test_member_alert_requires_bioguide(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})
    res = client.post("/api/account/alerts", json={"kind": "member_vote", "bioguideId": ""})
    assert res.status_code == 400


def test_invalid_alert_kind_rejected(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})
    res = client.post("/api/account/alerts", json={"kind": "spam_me", "bioguideId": ""})
    assert res.status_code == 400


def test_logout_clears_session(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})
    assert client.get("/api/account/me").status_code == 200
    assert client.post("/api/account/logout").status_code == 200
    assert client.get("/api/account/me").status_code == 401


def test_cross_site_write_rejected(client, sent):
    _register(client)
    client.post("/api/account/verify", json={"token": _token_for("user@example.org", "verify_email")})
    res = client.post(
        "/api/account/saved-members",
        json={"bioguideId": "A000055"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert res.status_code == 403
