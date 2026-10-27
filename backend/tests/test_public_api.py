import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.config import settings
from app.routes import public_api
from app.security import reset_rate_limits_for_tests

GOOD_KEY = "test-public-key-123"


@pytest.fixture
def client(monkeypatch):
    """App with no Congress client: services are monkeypatched per test."""
    monkeypatch.setattr(settings, "public_api_keys", GOOD_KEY)
    monkeypatch.setattr(settings, "public_api_rate_limit_per_hour", 1000)
    reset_rate_limits_for_tests()

    app = FastAPI()
    app.state.congress_client = object()
    app.include_router(public_api.router, prefix="/api")
    yield TestClient(app)
    reset_rate_limits_for_tests()


def _fake_members():
    return (
        [
            {
                "bioguideId": "A000055",
                "name": "Aderholt, Robert B.",
                "chamber": "House",
                "state": "Alabama",
                "stateCode": "AL",
                "party": "Republican",
                "district": 4,
                "imageUrl": None,
                "congressUrl": "https://www.congress.gov/member/A000055",
            }
        ],
        1,
    )


def test_public_api_disabled_without_keys(monkeypatch):
    monkeypatch.setattr(settings, "public_api_keys", "")
    reset_rate_limits_for_tests()

    app = FastAPI()
    app.state.congress_client = object()
    app.include_router(public_api.router, prefix="/api")

    response = TestClient(app).get("/api/public/v1/members")
    assert response.status_code == 503
    assert response.json()["detail"] == "Public API is not enabled"


def test_public_api_rejects_missing_key(client):
    response = client.get("/api/public/v1/bills")
    assert response.status_code == 401
    assert "X-API-Key" in response.json()["detail"]


def test_public_api_rejects_bad_key(client):
    for bad in ("wrong-key", " ", GOOD_KEY + "x"):
        response = client.get(
            "/api/public/v1/members", headers={"X-API-Key": bad}
        )
        assert response.status_code == 401, bad


def test_public_members_returns_directory(client, monkeypatch):
    calls = {}

    async def fake_build_directory(_client, congress, **kwargs):
        calls["congress"] = congress
        calls.update(kwargs)
        return _fake_members()

    monkeypatch.setattr(public_api, "build_directory", fake_build_directory)

    response = client.get(
        "/api/public/v1/members",
        headers={"X-API-Key": GOOD_KEY},
        params={"state": "Alabama", "limit": 5},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert body["offset"] == 0
    assert body["limit"] == 5
    assert body["members"][0]["bioguideId"] == "A000055"
    assert calls["congress"] == settings.congress_number
    assert calls["state"] == "Alabama"
    assert calls["limit"] == 5


def test_public_bills_returns_summary(client, monkeypatch):
    async def fake_get_bills_summary(_client):
        return [
            {
                "id": "119-hr-6484",
                "congress": 119,
                "number": "HR 6484",
                "title": "Kids Online Safety Act",
                "category": "Online Safety",
                "description": "Test description",
                "congressUrl": "https://www.congress.gov/bill/119/house-bill/6484",
                "floorStatus": "house_roll_call",
                "floorStatusLabel": "House roll call",
                "scorable": True,
            }
        ]

    monkeypatch.setattr(public_api, "get_bills_summary", fake_get_bills_summary)

    response = client.get(
        "/api/public/v1/bills", headers={"X-API-Key": GOOD_KEY}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["congress"] == settings.congress_number
    assert body["bills"][0]["number"] == "HR 6484"


def test_public_api_quota_returns_429(client, monkeypatch):
    monkeypatch.setattr(settings, "public_api_rate_limit_per_hour", 1)

    async def fake_get_bills_summary(_client):
        return []

    monkeypatch.setattr(public_api, "get_bills_summary", fake_get_bills_summary)

    headers = {"X-API-Key": GOOD_KEY}
    assert client.get("/api/public/v1/bills", headers=headers).status_code == 200
    assert client.get("/api/public/v1/bills", headers=headers).status_code == 429


def test_require_api_key_returns_canonical_key(monkeypatch):
    monkeypatch.setattr(settings, "public_api_keys", "first, second")
    assert public_api.require_api_key("second") == "second"
