"""Shared request security helpers: client IP, rate limits, input validation, safe errors."""

from __future__ import annotations

import logging
import re
import time
from collections import defaultdict
from threading import Lock

from fastapi import HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

logger = logging.getLogger(__name__)

# Baseline headers for API responses (Caddy may add more at the edge for HTML).
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
    "Cross-Origin-Opener-Policy": "same-origin",
    "Cross-Origin-Resource-Policy": "same-origin",
    "Cache-Control": "no-store",
}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach security headers to every HTTP response."""

    def __init__(self, app: ASGIApp, extra_headers: dict[str, str] | None = None):
        super().__init__(app)
        self.headers = {**SECURITY_HEADERS, **(extra_headers or {})}

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        for key, value in self.headers.items():
            if key not in response.headers:
                response.headers[key] = value
        return response


# Bioguide IDs are one letter + 6 digits (e.g. A000055). Allow a little slack for edge cases.
_BIOGUIDE_RE = re.compile(r"^[A-Za-z][0-9]{5,7}$")

# Tracked Congress sessions in modern API usage; keep a tight bound for DoS resistance.
MIN_CONGRESS = 100
MAX_CONGRESS = 200

_rate_lock = Lock()
# bucket -> ip -> timestamps
_rate_hits: dict[str, dict[str, list[float]]] = defaultdict(dict)
# Cap distinct IPs tracked per bucket to limit memory growth from spoofed keys.
_MAX_IPS_PER_BUCKET = 10_000


def client_ip(request: Request) -> str:
    """Resolve client IP behind a trusted reverse proxy (Caddy).

    Prefer X-Real-IP (set/overwritten by Caddy). For X-Forwarded-For, use the
    *rightmost* hop — Caddy appends the true peer, so leftmost values are
    client-spoofable and must not be used for rate limiting.
    """
    real_ip = (request.headers.get("x-real-ip") or "").strip()
    if real_ip and _looks_like_ip(real_ip):
        return real_ip.split("%")[0]  # strip IPv6 zone id if present

    forwarded = (request.headers.get("x-forwarded-for") or "").strip()
    if forwarded:
        parts = [p.strip() for p in forwarded.split(",") if p.strip()]
        if parts:
            candidate = parts[-1]
            if _looks_like_ip(candidate):
                return candidate.split("%")[0]

    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def _looks_like_ip(value: str) -> bool:
    # Lightweight check — not full validation; enough to reject obvious junk.
    if not value or len(value) > 64 or " " in value:
        return False
    return True


def rate_limit(
    ip: str,
    *,
    bucket: str,
    max_hits: int,
    window_seconds: float,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    """Sliding-window in-memory rate limit (per process)."""
    now = time.time()
    with _rate_lock:
        by_ip = _rate_hits[bucket]
        if ip not in by_ip and len(by_ip) >= _MAX_IPS_PER_BUCKET:
            # Evict oldest-looking entries roughly by clearing emptied lists first.
            stale = [k for k, hits in by_ip.items() if not hits]
            for k in stale[: max(1, len(stale))]:
                del by_ip[k]
            if ip not in by_ip and len(by_ip) >= _MAX_IPS_PER_BUCKET:
                # Drop an arbitrary key to bound memory under attack.
                by_ip.pop(next(iter(by_ip)))

        hits = [t for t in by_ip.get(ip, []) if now - t < window_seconds]
        if len(hits) >= max_hits:
            raise HTTPException(status_code=429, detail=detail)
        hits.append(now)
        by_ip[ip] = hits


def validate_bioguide_id(bioguide_id: str) -> str:
    value = (bioguide_id or "").strip()
    if not _BIOGUIDE_RE.match(value):
        raise HTTPException(status_code=400, detail="Invalid member id")
    # Canonical form: leading letter uppercase (e.g. A000055).
    return value[0].upper() + value[1:]


def validate_congress(congress: int | None, default: int) -> int:
    value = default if congress is None else congress
    if not isinstance(value, int) or value < MIN_CONGRESS or value > MAX_CONGRESS:
        raise HTTPException(status_code=400, detail="Invalid congress number")
    return value


_CREDENTIAL_PARAM_RE = re.compile(
    r"(?i)((?<![A-Za-z0-9_])"
    r"(?:api[_-]?key|x-api-key|apikey|access[_-]?token|auth(?:orization)?|password|passwd|secret|signature|token)"
    r"\s*=\s*)([^&\s\"']+)"
)


def _redact_credential_text(value: str) -> str:
    """Mask credential-bearing query parameters and key=value pairs in text."""
    return _CREDENTIAL_PARAM_RE.sub(r"\1[REDACTED]", value)


def safe_upstream_error(exc: Exception, *, public_message: str = "Upstream data source error") -> HTTPException:
    """Log a credential-redacted error server-side; never return secrets/URLs to clients."""
    text = str(exc)
    logger.warning("Upstream error (sanitized for client): %s", _redact_credential_text(text), exc_info=False)
    # Defense-in-depth if a caller still interpolates exception text somewhere.
    if "api_key=" in text.lower() or "x-api-key" in text.lower():
        logger.error("Refusing to surface exception text that may contain credentials")
    return HTTPException(status_code=502, detail=public_message)


def safe_service_error(exc: Exception, *, public_message: str = "Service temporarily unavailable") -> HTTPException:
    logger.warning("Service error (sanitized for client): %s", _redact_credential_text(str(exc)), exc_info=False)
    return HTTPException(status_code=503, detail=public_message)


def reset_rate_limits_for_tests() -> None:
    """Test helper."""
    with _rate_lock:
        _rate_hits.clear()
