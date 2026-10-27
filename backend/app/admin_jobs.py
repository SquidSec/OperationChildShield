"""Bookkeeping for the in-process background scheduler.

The scheduler loop lives elsewhere; this module only holds the shared state the
admin health panel reads, so it stays importable without starting any threads.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone

_lock = threading.Lock()
_last_run_at: str | None = None
_last_run_jobs: list[str] = []


def mark_run(jobs: list[str] | None = None) -> str:
    """Record that a scheduler tick finished; returns the ISO timestamp."""
    global _last_run_at, _last_run_jobs
    now = datetime.now(timezone.utc).isoformat()
    with _lock:
        _last_run_at = now
        _last_run_jobs = list(jobs or [])
    return now


def last_run() -> dict[str, object] | None:
    with _lock:
        if _last_run_at is None:
            return None
        return {"at": _last_run_at, "jobs": list(_last_run_jobs)}


def reset_for_tests() -> None:
    global _last_run_at, _last_run_jobs
    with _lock:
        _last_run_at = None
        _last_run_jobs = []
