import logging

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.security import (
    SecurityHeadersMiddleware,
    client_ip,
    rate_limit,
    reset_rate_limits_for_tests,
    safe_service_error,
    safe_upstream_error,
    validate_bioguide_id,
    validate_congress,
)


def test_validate_bioguide_id_accepts_canonical():
    assert validate_bioguide_id("A000055") == "A000055"
    assert validate_bioguide_id("a000055") == "A000055"


def test_validate_bioguide_id_rejects_junk():
    from fastapi import HTTPException

    for bad in ("", "../etc", "NOT_A_REAL_ID_ZZZZ", "A00", "../../x", "A000055/../x"):
        try:
            validate_bioguide_id(bad)
            assert False, f"expected reject for {bad!r}"
        except HTTPException as e:
            assert e.status_code == 400


def test_validate_congress_bounds():
    from fastapi import HTTPException

    assert validate_congress(None, 119) == 119
    assert validate_congress(119, 119) == 119
    try:
        validate_congress(1, 119)
        assert False
    except HTTPException as e:
        assert e.status_code == 400
    try:
        validate_congress(9999, 119)
        assert False
    except HTTPException as e:
        assert e.status_code == 400


def test_client_ip_prefers_x_real_ip_and_rightmost_xff():
    app = FastAPI()

    @app.get("/ip")
    def ip(request: Request):
        return {"ip": client_ip(request)}

    client = TestClient(app)

    # X-Real-IP wins
    r = client.get(
        "/ip",
        headers={
            "X-Real-IP": "198.51.100.10",
            "X-Forwarded-For": "203.0.113.1, 198.51.100.10",
        },
    )
    assert r.json()["ip"] == "198.51.100.10"

    # Without X-Real-IP, rightmost XFF is used (not leftmost spoof)
    r = client.get(
        "/ip",
        headers={"X-Forwarded-For": "203.0.113.50, 198.51.100.20"},
    )
    assert r.json()["ip"] == "198.51.100.20"


def test_rate_limit_trips():
    reset_rate_limits_for_tests()
    from fastapi import HTTPException

    for _ in range(3):
        rate_limit("1.2.3.4", bucket="t", max_hits=3, window_seconds=60)
    try:
        rate_limit("1.2.3.4", bucket="t", max_hits=3, window_seconds=60)
        assert False
    except HTTPException as e:
        assert e.status_code == 429


def test_safe_upstream_error_hides_secrets():
    exc = Exception(
        "Client error '404' for url 'https://api.congress.gov/v3/member/X?api_key=SECRET'"
    )
    err = safe_upstream_error(exc)
    assert err.status_code == 502
    assert "api_key" not in err.detail.lower()
    assert "SECRET" not in err.detail


def test_safe_upstream_error_redacts_secrets_from_logs(caplog):
    caplog.set_level(logging.WARNING)
    exc = Exception(
        "Client error '404' for url 'https://api.congress.gov/v3/member/X?api_key=SECRET'"
    )
    safe_upstream_error(exc)
    assert "SECRET" not in caplog.text
    assert "api_key=SECRET" not in caplog.text


def test_safe_service_error_redacts_secrets_from_logs(caplog):
    caplog.set_level(logging.WARNING)
    exc = Exception(
        "Request failed: https://example.com/data?x-api-key=TOPSECRET&foo=bar"
    )
    safe_service_error(exc)
    assert "TOPSECRET" not in caplog.text
    assert "x-api-key=TOPSECRET" not in caplog.text


def test_security_headers_middleware_sets_baseline():
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/ping")
    def ping():
        return {"ok": True}

    client = TestClient(app)
    r = client.get("/ping")
    assert r.status_code == 200
    assert r.headers.get("X-Content-Type-Options") == "nosniff"
    assert r.headers.get("X-Frame-Options") == "DENY"
    assert r.headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "camera=()" in (r.headers.get("Permissions-Policy") or "")
