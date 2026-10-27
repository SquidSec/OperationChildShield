"""Self-hosted proof-of-work captcha."""

import hashlib
import time

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app import captcha
from app.routes import admin
from app.security import reset_rate_limits_for_tests
from tests.captcha_helpers import get_challenge, solved_token


@pytest.fixture(autouse=True)
def _fresh():
    captcha.reset_for_tests()
    reset_rate_limits_for_tests()
    yield
    captcha.reset_for_tests()


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    # Isolate every DB path: these tests create admin accounts, which must not
    # touch the developer's data/ directory or leak between tests.
    from app import admin_store, analytics_store, applications_store

    for module in (admin_store, analytics_store, applications_store):
        monkeypatch.setattr(module.settings, "cache_dir", str(tmp_path))
    admin_store.reset_for_tests()
    analytics_store._initialized = False
    admin_store.init_admin_db()
    analytics_store.init_analytics_db()

    app = FastAPI()
    app.include_router(admin.router, prefix="/api")
    return TestClient(app)


# --- Challenge issuance -----------------------------------------------------


def test_issue_returns_random_parameters():
    first = captcha.issue_challenge(ip="203.0.113.9")
    second = captcha.issue_challenge(ip="203.0.113.9")
    assert first["challenge"] != second["challenge"]
    assert len(str(first["challenge"])) >= 32
    assert first["algorithm"] == "sha256-prefix-zeros"
    assert captcha.MIN_DIFFICULTY <= int(first["difficulty"]) <= captcha.MAX_DIFFICULTY
    assert int(first["expiresIn"]) == captcha.CHALLENGE_TTL_SECONDS


def test_difficulty_is_clamped_to_a_sane_range(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "pow_difficulty", 1)
    assert captcha._difficulty() == captcha.MIN_DIFFICULTY
    monkeypatch.setattr(settings, "pow_difficulty", 99)
    assert captcha._difficulty() == captcha.MAX_DIFFICULTY


def test_challenge_endpoint_is_public(client):
    res = client.get("/api/captcha/challenge")
    assert res.status_code == 200
    body = res.json()
    assert "challenge" in body and "difficulty" in body


def test_challenge_endpoint_is_rate_limited(client):
    statuses = {client.get("/api/captcha/challenge").status_code for _ in range(40)}
    assert 429 in statuses


# --- Solving and verification ----------------------------------------------


def test_reference_solver_produces_a_valid_solution():
    data = captcha.issue_challenge()
    solution = captcha.solve(str(data["challenge"]), int(data["difficulty"]))
    assert solution is not None
    assert captcha.verify_solution(str(data["challenge"]), str(solution["nonce"]))


def test_solution_hash_meets_the_difficulty():
    data = captcha.issue_challenge()
    difficulty = int(data["difficulty"])
    solution = captcha.solve(str(data["challenge"]), difficulty)
    digest = hashlib.sha256(
        f"{data['challenge']}:{solution['nonce']}".encode()
    ).digest()
    assert captcha._leading_zero_bits(digest) >= difficulty


def test_wrong_nonce_is_rejected():
    data = captcha.issue_challenge()
    # Nonce 0 almost never satisfies 17 bits; verify it is actually checked.
    valid = captcha.verify_solution(str(data["challenge"]), "0")
    digest = hashlib.sha256(f"{data['challenge']}:0".encode()).digest()
    if captcha._leading_zero_bits(digest) < int(data["difficulty"]):
        assert valid is False


def test_challenge_is_single_use():
    data = captcha.issue_challenge()
    solution = captcha.solve(str(data["challenge"]), int(data["difficulty"]))
    assert captcha.verify_solution(str(data["challenge"]), str(solution["nonce"])) is True
    # Second attempt: the challenge is gone.
    assert captcha.verify_solution(str(data["challenge"]), str(solution["nonce"])) is False


def test_unknown_challenge_is_rejected():
    assert captcha.verify_solution("deadbeef" * 6, "12345") is False


def test_expired_challenge_is_rejected(monkeypatch):
    data = captcha.issue_challenge()
    solution = captcha.solve(str(data["challenge"]), int(data["difficulty"]))
    # Move the clock past the TTL.
    real_time = time.time
    monkeypatch.setattr(captcha.time, "time", lambda: real_time() + captcha.CHALLENGE_TTL_SECONDS + 5)
    assert captcha.verify_solution(str(data["challenge"]), str(solution["nonce"])) is False


def test_challenge_bound_to_a_different_ip_is_rejected():
    data = captcha.issue_challenge(ip="203.0.113.9")
    solution = captcha.solve(str(data["challenge"]), int(data["difficulty"]))
    assert (
        captcha.verify_solution(
            str(data["challenge"]), str(solution["nonce"]), ip="198.51.100.7"
        )
        is False
    )


def test_malformed_solutions_are_rejected():
    data = captcha.issue_challenge()
    challenge = str(data["challenge"])
    for bad in ("", "abc", "-1", "1.5", "9" * 40, " "):
        assert captcha.verify_solution(challenge, bad) is False


def test_client_reported_hash_mismatch_still_passes_when_recomputation_matches():
    """The server recomputes; a wrong client-reported hash is only logged."""
    data = captcha.issue_challenge()
    solution = captcha.solve(str(data["challenge"]), int(data["difficulty"]))
    assert captcha.verify_solution(
        str(data["challenge"]), str(solution["nonce"]), claimed_hash="00" * 32
    ) is True


def test_pending_challenges_are_bounded(monkeypatch):
    monkeypatch.setattr(captcha, "MAX_PENDING_CHALLENGES", 3)
    for _ in range(3):
        captcha.issue_challenge()
    assert captcha.pending_count() == 3
    with pytest.raises(RuntimeError):
        captcha.issue_challenge()


def test_expired_challenges_are_swept(monkeypatch):
    monkeypatch.setattr(captcha, "MAX_PENDING_CHALLENGES", 2)
    captcha.issue_challenge()
    captcha.issue_challenge()
    # Expire everything, then a new issue must succeed after the sweep.
    real_time = time.time
    monkeypatch.setattr(captcha.time, "time", lambda: real_time() + captcha.CHALLENGE_TTL_SECONDS + 5)
    captcha.issue_challenge()
    assert captcha.pending_count() == 1


# --- Leading-zero helper ----------------------------------------------------


@pytest.mark.parametrize(
    "digest,expected",
    [
        (b"\x00\x00", 16),
        (b"\x00\x01", 15),
        (b"\x80", 0),
        (b"\x40", 1),
        (b"\x00\x00\x80", 16),
    ],
)
def test_leading_zero_bits(digest, expected):
    assert captcha._leading_zero_bits(digest) == expected


# --- Login integration ------------------------------------------------------


def test_login_rejects_a_replayed_token(client):
    from app import admin_store

    admin_store.upsert_admin("replay@example.org", "harbor lantern velvet quartz", role="owner")
    token = solved_token(client)
    first = client.post(
        "/api/admin/login",
        json={"email": "replay@example.org", "password": "harbor lantern velvet quartz", "captcha_token": token},
    )
    assert first.status_code == 200
    client.cookies.clear()
    second = client.post(
        "/api/admin/login",
        json={"email": "replay@example.org", "password": "harbor lantern velvet quartz", "captcha_token": token},
    )
    assert second.status_code == 400


def test_login_rejects_an_unsolved_token(client):
    from app import admin_store

    admin_store.upsert_admin("unsolved@example.org", "harbor lantern velvet quartz", role="owner")
    data = get_challenge(client)
    res = client.post(
        "/api/admin/login",
        json={
            "email": "unsolved@example.org",
            "password": "harbor lantern velvet quartz",
            "captcha_token": f"{data['challenge']}.0",
        },
    )
    assert res.status_code in (400, 401)
    assert "ocs_admin_session" not in res.cookies
