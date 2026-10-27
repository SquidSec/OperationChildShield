"""Rate limiting with an optional shared Redis backend.

The in-process limiter in ``app.security`` is correct for a single instance but
resets on deploy and cannot span replicas. Configure ``REDIS_URL`` to share
counters; any Redis error falls back to the in-process limiter so a cache outage
cannot take login down (with the tradeoff that limits become per-process).

The ``redis`` package is optional and imported lazily, so deployments that do
not use it need no extra dependency. Tests inject a fake client through
:func:`set_client_for_tests` (the module-level ``_client`` hook) and never touch
the network.
"""

from __future__ import annotations

import logging
import threading

from fastapi import HTTPException

from app.config import settings
from app.security import rate_limit as _local_rate_limit

logger = logging.getLogger(__name__)

_lock = threading.Lock()
_client = None
_client_attempted = False
_client_disabled = False
_warned_unavailable = False


def _get_client():
    """Return a Redis client, or None when unavailable. Cached after first use."""
    global _client, _client_attempted, _client_disabled, _warned_unavailable

    if _client is not None:
        return _client
    if _client_disabled or not settings.redis_url:
        return None
    with _lock:
        if _client is not None:
            return _client
        if _client_attempted:
            return _client
        _client_attempted = True
        try:
            import redis  # type: ignore[import-not-found]

            candidate = redis.Redis.from_url(
                settings.redis_url,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
                decode_responses=True,
            )
            candidate.ping()
            _client = candidate
            logger.info("Shared rate limiting enabled via Redis")
        except Exception:
            if not _warned_unavailable:
                logger.warning(
                    "Redis unavailable for rate limiting; using in-process limits. "
                    "Limits reset on restart and are per-process."
                )
                _warned_unavailable = True
            _client_disabled = True
            _client = None
        return _client


def _redis_check(
    client,
    key: str,
    *,
    bucket: str,
    max_hits: int,
    window_seconds: float,
    detail: str,
) -> None:
    """Fixed-window counter: INCR on every hit, EXPIRE on the first of a window."""
    redis_key = f"ratelimit:{bucket}:{key}"
    count = int(client.incr(redis_key))
    if count == 1:
        client.expire(redis_key, max(1, int(window_seconds)))
    if count > max_hits:
        raise HTTPException(status_code=429, detail=detail)


def check_rate_limit(
    key: str,
    *,
    bucket: str,
    max_hits: int,
    window_seconds: float,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    """Enforce a limit, preferring Redis when configured and reachable.

    Raises ``HTTPException(429)`` when the limit is exceeded.
    """
    client = _get_client()
    if client is not None:
        try:
            _redis_check(
                client,
                key,
                bucket=bucket,
                max_hits=max_hits,
                window_seconds=window_seconds,
                detail=detail,
            )
            return
        except HTTPException:
            raise
        except Exception:
            logger.warning("Redis rate limit check failed; falling back to local", exc_info=False)

    _local_rate_limit(
        key,
        bucket=bucket,
        max_hits=max_hits,
        window_seconds=window_seconds,
        detail=detail,
    )


def backend_name() -> str:
    """``"redis"`` when the shared backend is in use, else ``"process"``."""
    return "redis" if _get_client() is not None else "process"


def set_client_for_tests(client) -> None:
    """Inject a fake Redis client (or None to force the in-process path)."""
    global _client, _client_attempted, _client_disabled
    with _lock:
        _client = client
        _client_attempted = True
        _client_disabled = client is None


def reset_for_tests() -> None:
    """Forget the cached client so the next call re-resolves the backend."""
    global _client, _client_attempted, _client_disabled, _warned_unavailable
    with _lock:
        _client = None
        _client_attempted = False
        _client_disabled = False
        _warned_unavailable = False
