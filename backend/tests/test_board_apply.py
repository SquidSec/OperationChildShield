import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import analytics_store, users_store
from app.routes import board
from app.security import reset_rate_limits_for_tests


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(board.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(users_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(board.settings, "admin_captcha_disabled", False)
    monkeypatch.setattr(board.settings, "turnstile_secret_key", "")
    reset_rate_limits_for_tests()

    async def fake_verify(token: str, *, remote_ip: str | None = None) -> bool:
        return token == "valid-token"

    monkeypatch.setattr(board, "verify_turnstile", fake_verify)
    monkeypatch.setattr(board, "_notify_application", lambda record: None)

    app = FastAPI()
    app.include_router(board.router, prefix="/api")
    return TestClient(app)


def _payload(**overrides):
    body = {
        "role": "vice-president",
        "name": "Jane Applicant",
        "email": "jane@example.org",
        "phone": "555-0100",
        "location": "Austin, TX",
        "linkedin": "https://example.org/jane",
        "statement": "I have served on two nonprofit boards.",
        "consent": True,
        "captcha_token": "valid-token",
        "website": "",
    }
    body.update(overrides)
    return body


def test_application_persists_with_captcha(client, tmp_path):
    res = client.post("/api/board/apply", json=_payload())
    assert res.status_code == 200
    assert res.json()["ok"] is True

    path = tmp_path / "board_applications.jsonl"
    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["email"] == "jane@example.org"
    assert record["role"] == "vice-president"
    assert record["roleLabel"] == "Vice President"
    assert "submittedAt" in record


def test_application_rejected_without_captcha(client, tmp_path):
    res = client.post("/api/board/apply", json=_payload(captcha_token=""))
    assert res.status_code == 400
    assert "captcha" in res.json()["detail"].lower()
    assert not (tmp_path / "board_applications.jsonl").exists()


def test_application_rejected_with_invalid_captcha(client):
    res = client.post("/api/board/apply", json=_payload(captcha_token="bogus"))
    assert res.status_code == 400


def test_application_requires_consent(client):
    res = client.post("/api/board/apply", json=_payload(consent=False))
    assert res.status_code == 400
    assert "contact" in res.json()["detail"].lower()


def test_application_rejects_closed_role(client):
    res = client.post("/api/board/apply", json=_payload(role="president"))
    assert res.status_code == 400
    assert "not open" in res.json()["detail"].lower()


def test_application_rejects_invalid_email(client):
    res = client.post("/api/board/apply", json=_payload(email="not-an-email"))
    assert res.status_code == 422


def test_honeypot_returns_silent_success(client, tmp_path):
    res = client.post("/api/board/apply", json=_payload(website="http://spam.example"))
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert not (tmp_path / "board_applications.jsonl").exists()


def test_application_requires_statement(client):
    res = client.post("/api/board/apply", json=_payload(statement=""))
    assert res.status_code == 422
