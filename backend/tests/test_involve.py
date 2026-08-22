import json
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import analytics_store
from app.routes import involve


def _app(tmp_path: Path, monkeypatch) -> TestClient:
    monkeypatch.setattr(involve.settings, "cache_dir", str(tmp_path))
    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    analytics_store._initialized = False
    app = FastAPI()
    app.include_router(involve.router, prefix="/api")
    return TestClient(app)


def test_involve_signup_persists_jsonl(tmp_path, monkeypatch):
    sent: list[dict] = []

    def fake_notify(record):
        sent.append(record)
        return True

    monkeypatch.setattr(involve, "notify_involve_signup", fake_notify)
    monkeypatch.setattr(involve, "auto_reply_involve_signup", lambda _r: False)

    client = _app(tmp_path, monkeypatch)
    res = client.post(
        "/api/involve",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "state": "Texas",
            "interest": "volunteer",
            "message": "Happy to help",
            "consent": True,
            "website": "",
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True

    path = tmp_path / "involve_signups.jsonl"
    assert path.exists()
    record = json.loads(path.read_text(encoding="utf-8").strip())
    assert record["email"] == "jane@example.com"
    assert record["interest"] == "volunteer"
    assert record["state"] == "Texas"
    assert "submittedAt" in record
    assert len(sent) == 1
    assert sent[0]["email"] == "jane@example.com"


def test_involve_signup_succeeds_when_smtp_fails(tmp_path, monkeypatch):
    def boom(_record):
        raise RuntimeError("smtp down")

    monkeypatch.setattr(involve, "notify_involve_signup", boom)
    monkeypatch.setattr(involve, "auto_reply_involve_signup", boom)

    client = _app(tmp_path, monkeypatch)
    res = client.post(
        "/api/involve",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "consent": True,
        },
    )
    assert res.status_code == 200
    assert res.json()["ok"] is True
    assert (tmp_path / "involve_signups.jsonl").exists()


def test_involve_requires_consent(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch)
    res = client.post(
        "/api/involve",
        json={
            "name": "Jane Doe",
            "email": "jane@example.com",
            "consent": False,
        },
    )
    assert res.status_code == 400


def test_involve_honeypot_silent_success(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch)
    res = client.post(
        "/api/involve",
        json={
            "name": "Bot",
            "email": "bot@example.com",
            "consent": True,
            "website": "http://spam.example",
        },
    )
    assert res.status_code == 200
    assert not (tmp_path / "involve_signups.jsonl").exists()


def test_involve_rejects_bad_email(tmp_path, monkeypatch):
    client = _app(tmp_path, monkeypatch)
    res = client.post(
        "/api/involve",
        json={
            "name": "Jane",
            "email": "not-an-email",
            "consent": True,
        },
    )
    assert res.status_code == 422
