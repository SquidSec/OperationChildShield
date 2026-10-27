"""Cloudflare Turnstile verification for the admin login.

Fail-closed: a missing secret rejects every login unless ADMIN_CAPTCHA_DISABLED
is explicitly set (local development only). Cloudflare's documented test keys
work in development while keeping the real verification path exercised.
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"
_TIMEOUT_SECONDS = 5.0

# Cloudflare's documented test keys always report hostname "example.com", so
# hostname enforcement is skipped only when one of these is configured.
_TEST_SECRET_KEYS = frozenset(
    {
        "1x0000000000000000000000000000000AA",  # always passes
        "2x0000000000000000000000000000000AA",  # always fails
        "3x0000000000000000000000000000000AA",  # forces a challenge
    }
)


class CaptchaError(Exception):
    """Raised when a login should be rejected because of captcha state."""


def captcha_configured() -> bool:
    return bool(settings.turnstile_site_key and settings.turnstile_secret_key)


async def verify_turnstile(token: str, *, remote_ip: str | None = None) -> bool:
    """Validate a Turnstile response token with Cloudflare's siteverify API."""
    if settings.admin_captcha_disabled and not settings.turnstile_secret_key:
        logger.warning("Admin captcha disabled by configuration; do not use in production")
        return True
    if not settings.turnstile_secret_key:
        logger.error("Admin login rejected: TURNSTILE_SECRET_KEY is not configured")
        return False

    value = (token or "").strip()
    if not value or len(value) > 2048:
        return False

    payload = {"secret": settings.turnstile_secret_key, "response": value}
    if remote_ip and remote_ip != "unknown":
        payload["remoteip"] = remote_ip

    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            response = await client.post(_VERIFY_URL, data=payload)
            response.raise_for_status()
            result = response.json()
    except (httpx.HTTPError, ValueError):
        logger.warning("Turnstile verification unavailable; failing closed")
        return False

    if not result.get("success"):
        logger.info("Turnstile rejected login: %s", result.get("error-codes"))
        return False

    # If Cloudflare returns a hostname, it must be one we expect. Test keys
    # report example.com, so skip the check for those only.
    hostname = (result.get("hostname") or "").lower()
    allowed = settings.admin_allowed_hostname_list
    using_test_key = settings.turnstile_secret_key in _TEST_SECRET_KEYS
    if hostname and allowed and not using_test_key and hostname not in allowed:
        logger.warning("Turnstile hostname not allowed: %s", hostname)
        return False

    return True
