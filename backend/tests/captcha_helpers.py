"""Helpers for the self-hosted proof-of-work captcha in tests.

Tests solve a real challenge rather than mocking verification, so the whole
path is exercised: issue, solve, submit, burn.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app import captcha


def get_challenge(client: TestClient) -> dict[str, object]:
    res = client.get("/api/captcha/challenge")
    assert res.status_code == 200, res.text
    return res.json()


def solved_token(client: TestClient) -> str:
    """Issue and solve a challenge, returning '<challenge>.<nonce>'."""
    data = get_challenge(client)
    solution = captcha.solve(str(data["challenge"]), int(data["difficulty"]))
    assert solution is not None, "reference solver failed to find a nonce"
    return f"{data['challenge']}.{solution['nonce']}"


def solved_token_for(challenge: str, difficulty: int) -> str:
    solution = captcha.solve(challenge, difficulty)
    assert solution is not None
    return f"{challenge}.{solution['nonce']}"
