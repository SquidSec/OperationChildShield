import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import analytics_store, captcha, users_store
from app.routes import admin, board
from app.security import reset_rate_limits_for_tests
from tests.captcha_helpers import solved_token


@pytest.fixture
def client(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(board.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(users_store.settings, "cache_dir", str(tmp_path))
    reset_rate_limits_for_tests()
    captcha.reset_for_tests()
    monkeypatch.setattr(board, "_notify_application", lambda record: None)

    app = FastAPI()
    # The challenge endpoint lives on the admin router; mount it so tests can
    # solve a real challenge instead of mocking verification.
    app.include_router(admin.router, prefix="/api")
    app.include_router(board.router, prefix="/api")
    return TestClient(app)


def _payload(client=None, **overrides):
    body = {
        "role": "vice-president",
        "name": "Jane Applicant",
        "email": "jane@example.org",
        "phone": "555-0100",
        "location": "Austin, TX",
        "linkedin": "https://example.org/jane",
        "statement": "I have served on two nonprofit boards.",
        "consent": True,
        "captcha_token": "",
        "website": "",
    }
    body.update(overrides)
    return body


def test_application_persists_with_captcha(client, tmp_path):
    res = client.post("/api/board/apply", json=_payload(captcha_token=solved_token(client)))
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
    res = client.post("/api/board/apply", json=_payload(captcha_token=solved_token(client), consent=False))
    assert res.status_code == 400
    assert "contact" in res.json()["detail"].lower()


def test_application_rejects_closed_role(client):
    res = client.post("/api/board/apply", json=_payload(captcha_token=solved_token(client), role="president"))
    assert res.status_code == 400
    assert "not open" in res.json()["detail"].lower()


def test_application_rejects_invalid_email(client):
    res = client.post("/api/board/apply", json=_payload(captcha_token=solved_token(client), email="not-an-email"))
    assert res.status_code == 422


def test_honeypot_returns_silent_success(client, tmp_path):
    res = client.post("/api/board/apply", json=_payload(captcha_token=solved_token(client), website="http://spam.example"))
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert not (tmp_path / "board_applications.jsonl").exists()


def test_application_requires_statement(client):
    res = client.post("/api/board/apply", json=_payload(captcha_token=solved_token(client), statement=""))
    assert res.status_code == 422
