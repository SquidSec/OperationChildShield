import threading
import time

import pytest

from app import jobs


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    monkeypatch.setattr(jobs.settings, "scheduler_enabled", True)
    monkeypatch.setattr(jobs.settings, "scheduler_interval_seconds", 1)
    monkeypatch.setattr(jobs.settings, "skip_bill_verification", True)
    jobs.reset_for_tests()
    yield
    jobs.reset_for_tests()


def test_register_and_scheduler_state():
    jobs.register("noop", 60, lambda: "ok")

    state = jobs.scheduler_state()

    assert state["running"] is False
    assert [job["name"] for job in state["jobs"]] == ["noop"]
    job = state["jobs"][0]
    assert job["last_run"] is None
    assert job["last_error"] is None
    assert job["next_run"] is not None


def test_register_clamps_interval():
    jobs.register("fast", 0.1, lambda: None)
    assert jobs.scheduler_state()["jobs"][0]["next_run"] is not None


def test_start_is_idempotent():
    jobs.register("noop", 60, lambda: None)

    assert jobs.start_scheduler() is True
    assert jobs.start_scheduler() is False
    assert jobs.scheduler_state()["running"] is True

    jobs.stop_scheduler()
    assert jobs.scheduler_state()["running"] is False


def test_stop_is_idempotent():
    jobs.register("noop", 60, lambda: None)
    jobs.start_scheduler()

    assert jobs.stop_scheduler() is True
    # Already stopped: no thread to join.
    assert jobs.stop_scheduler() is False


def test_start_disabled_returns_false(monkeypatch):
    monkeypatch.setattr(jobs.settings, "scheduler_enabled", False)
    jobs.register("noop", 60, lambda: None)

    assert jobs.start_scheduler() is False
    assert jobs.scheduler_state()["running"] is False


def test_zero_interval_disables_scheduler(monkeypatch):
    monkeypatch.setattr(jobs.settings, "scheduler_interval_seconds", 0)
    jobs.register("noop", 60, lambda: None)

    assert jobs.start_scheduler() is False
    assert jobs.scheduler_state()["running"] is False


def test_run_job_now_records_success():
    jobs.register("ok", 60, lambda: "value")
    assert jobs.run_job_now("ok") == "value"
    # Registering a callable that returns a value also updates state.
    job = jobs.scheduler_state()
    assert job["last_run"] is not None
    assert job["last_error"] is None


def test_run_job_now_captures_error():
    def boom():
        raise RuntimeError("kaboom")

    jobs.register("boom", 60, boom)

    assert jobs.run_job_now("boom") is None
    state = jobs.scheduler_state()
    assert "RuntimeError: kaboom" in state["jobs"][0]["last_error"]
    assert "boom" in state["last_error"]


def test_run_unknown_job_raises():
    with pytest.raises(KeyError):
        jobs.run_job_now("nope")


def test_failing_job_does_not_kill_thread():
    """A job that raises must not stop the loop; later ticks keep working."""
    hits: list[str] = []

    def boom():
        hits.append("boom")
        raise RuntimeError("kaboom")

    def ok():
        hits.append("ok")

    jobs.register("boom", 1, boom)
    jobs.register("ok", 1, ok)
    # Make both immediately due so the first tick within the test runs them.
    for job in jobs._jobs.values():
        job["next_run"] = 0.0

    thread = threading.Thread(target=jobs._loop, args=(0.01,), daemon=True)
    thread.start()
    try:
        deadline = time.time() + 3
        while time.time() < deadline and len(hits) < 4:
            time.sleep(0.02)
    finally:
        jobs._stop_event.set()
        thread.join(timeout=2)

    assert thread.is_alive() is False
    assert hits.count("boom") >= 2
    assert hits.count("ok") >= 2
    assert jobs.scheduler_state()["jobs"][0]["next_run"] is not None


def test_due_jobs_mark_admin_run():
    from app import admin_jobs

    admin_jobs.reset_for_tests()
    jobs.register("ok", 1, lambda: None)
    for job in jobs._jobs.values():
        job["next_run"] = 0.0

    jobs._run_due_jobs()

    assert admin_jobs.last_run()["jobs"] == ["ok"]
    admin_jobs.reset_for_tests()


def test_default_jobs_are_registered_on_start():
    jobs.start_scheduler()
    try:
        names = {job["name"] for job in jobs.scheduler_state()["jobs"]}
    finally:
        jobs.stop_scheduler()
    assert names == {
        "prune_analytics",
        "send_alerts",
        "verify_bills",
        "reclassify_traffic",
    }


def test_verify_bills_skips_when_flagged():
    assert jobs._verify_bills() == "skipped"


def test_verify_bills_uses_client(monkeypatch):
    calls: list[str] = []

    async def fake_log(client):
        calls.append("logged")

    class FakeClient:
        closed = False

        async def close(self):
            FakeClient.closed = True

    monkeypatch.setattr(jobs.settings, "skip_bill_verification", False)
    monkeypatch.setattr("app.bill_verification.log_bill_verification", fake_log)
    monkeypatch.setattr("app.congress_client.CongressClient", lambda: FakeClient())

    assert jobs._verify_bills() == "ok"
    assert calls == ["logged"]
    assert FakeClient.closed is True


def test_prune_analytics_uses_retention_prune(monkeypatch, tmp_path):
    from app import analytics_store

    monkeypatch.setattr(analytics_store.settings, "cache_dir", str(tmp_path))
    analytics_store._initialized = False
    try:
        result = jobs._prune_analytics()
    finally:
        analytics_store._initialized = False

    assert result == {"page_views": 0, "action_events": 0}


def test_send_alerts_delegates(monkeypatch):
    monkeypatch.setattr(
        "app.alerts.dispatch_pending_alerts",
        lambda: {"sent": 1, "failed": 0, "skipped": 0},
    )
    assert jobs._send_alerts() == {"sent": 1, "failed": 0, "skipped": 0}
