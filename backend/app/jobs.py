"""Minimal in-process background job scheduler (stdlib only).

A single daemon thread wakes on ``settings.scheduler_interval_seconds`` and runs
any job whose ``next_run`` has passed. This is deliberately small: it keeps
periodic maintenance (analytics housekeeping, alert delivery, bill verification)
off the request path without adding a broker or worker container.

Job failures are recorded in :func:`scheduler_state` and never kill the thread —
one broken job must not stop the others from running.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any, Callable

from app.config import settings

logger = logging.getLogger(__name__)

JobFn = Callable[[], Any]

_state_lock = threading.Lock()
_jobs: dict[str, dict[str, Any]] = {}
_thread: threading.Thread | None = None
_stop_event = threading.Event()
_last_run: float | None = None
_last_error: str | None = None
_defaults_registered = False


def register(name: str, interval_seconds: float, fn: JobFn) -> None:
    """Register (or replace) a job. Interval is clamped to at least one second."""
    interval = max(1.0, float(interval_seconds))
    now = time.time()
    with _state_lock:
        _jobs[name] = {
            "fn": fn,
            "interval": interval,
            "last_run": None,
            "last_error": None,
            "next_run": now + interval,
        }


def _prune_analytics() -> dict[str, int]:
    """Drop analytics rows past the retention window."""
    from app import analytics_store

    return analytics_store.prune_expired_now()


def _send_alerts() -> dict[str, int]:
    from app import alerts

    return alerts.dispatch_pending_alerts()


def _reclassify_traffic():
    from app.analytics_store import reclassify_page_views

    return reclassify_page_views(batch=2000)


def _verify_bills() -> str:
    if settings.skip_bill_verification:
        return "skipped"

    from app.bill_verification import log_bill_verification
    from app.congress_client import CongressClient

    async def _run() -> None:
        client = CongressClient()
        try:
            await log_bill_verification(client)
        finally:
            await client.close()

    asyncio.run(_run())
    return "ok"


def _register_defaults() -> None:
    global _defaults_registered
    with _state_lock:
        if _defaults_registered:
            return
        _defaults_registered = True
    interval = max(1, int(settings.scheduler_interval_seconds))
    register("prune_analytics", interval * 12, _prune_analytics)
    register("send_alerts", interval, _send_alerts)
    register("verify_bills", interval * 24, _verify_bills)
    # Widening the bot rules should apply to history, not only new hits.
    register("reclassify_traffic", interval * 6, _reclassify_traffic)


def _execute(name: str, job: dict[str, Any]) -> Any:
    """Run one job, recording success/failure and never raising."""
    global _last_run, _last_error
    started = time.time()
    try:
        result = job["fn"]()
    except Exception as exc:  # noqa: BLE001 - jobs must not kill the thread
        message = f"{type(exc).__name__}: {exc}"[:500]
        logger.exception("Background job %s failed", name)
        with _state_lock:
            job["last_error"] = message
            job["last_run"] = started
            job["next_run"] = started + job["interval"]
            _last_run = started
            _last_error = f"{name}: {message}"
        return None

    with _state_lock:
        job["last_run"] = started
        job["last_error"] = None
        job["next_run"] = started + job["interval"]
        _last_run = started
    logger.debug("Background job %s finished", name)
    return result


def run_job_now(name: str) -> Any:
    """Run a registered job synchronously. Returns its result, or None on error."""
    with _state_lock:
        job = _jobs.get(name)
    if job is None:
        raise KeyError(f"Unknown job: {name}")
    return _execute(name, job)


def _run_due_jobs() -> None:
    now = time.time()
    with _state_lock:
        due = [
            (name, job)
            for name, job in _jobs.items()
            if job["next_run"] is None or job["next_run"] <= now
        ]
    ran: list[str] = []
    for name, job in due:
        _execute(name, job)
        ran.append(name)

    if ran:
        # The admin health panel reads this separate store; keep it in sync.
        try:
            from app import admin_jobs

            admin_jobs.mark_run(ran)
        except Exception:  # noqa: BLE001 - bookkeeping must not break the tick
            logger.warning("Failed to record scheduler run in admin_jobs", exc_info=True)


def _loop(tick_seconds: float) -> None:
    while not _stop_event.wait(tick_seconds):
        try:
            _run_due_jobs()
        except Exception:  # noqa: BLE001 - keep the scheduler alive
            logger.exception("Scheduler tick failed")


def start_scheduler() -> bool:
    """Start the scheduler thread. Returns False when disabled or already running."""
    global _thread

    if not settings.scheduler_enabled:
        logger.info("Scheduler disabled (SCHEDULER_ENABLED=0)")
        return False

    tick_seconds = max(1, int(settings.scheduler_interval_seconds or 0))
    if int(settings.scheduler_interval_seconds or 0) <= 0:
        logger.info("Scheduler disabled (SCHEDULER_INTERVAL_SECONDS=0)")
        return False

    _register_defaults()

    with _state_lock:
        if _thread is not None and _thread.is_alive():
            return False
        _stop_event.clear()
        thread = threading.Thread(
            target=_loop,
            args=(tick_seconds,),
            name="ocs-scheduler",
            daemon=True,
        )
        _thread = thread
    thread.start()
    logger.info("Background scheduler started (tick=%ss)", tick_seconds)
    return True


def stop_scheduler(timeout: float = 5.0) -> bool:
    """Signal the scheduler thread to exit. Idempotent."""
    global _thread

    with _state_lock:
        thread = _thread
        _thread = None
    _stop_event.set()
    if thread is None:
        return False
    if thread.is_alive():
        thread.join(timeout=timeout)
    return True


def is_running() -> bool:
    with _state_lock:
        return _thread is not None and _thread.is_alive()


def _iso(ts: float | None) -> str | None:
    if ts is None:
        return None
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


def scheduler_state() -> dict[str, Any]:
    """Snapshot for admin/health endpoints."""
    with _state_lock:
        jobs = [
            {
                "name": name,
                "last_run": _iso(job["last_run"]),
                "last_error": job["last_error"],
                "next_run": _iso(job["next_run"]),
            }
            for name, job in sorted(_jobs.items())
        ]
        return {
            "running": _thread is not None and _thread.is_alive(),
            "last_run": _iso(_last_run),
            "last_error": _last_error,
            "jobs": jobs,
        }


def reset_for_tests() -> None:
    """Stop the thread and forget all registrations."""
    global _defaults_registered, _last_run, _last_error
    stop_scheduler()
    with _state_lock:
        _jobs.clear()
        _defaults_registered = False
        _last_run = None
        _last_error = None
    _stop_event.clear()
