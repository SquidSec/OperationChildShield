from fastapi import HTTPException
import pytest

from app import rate_limit_redis
from app.security import reset_rate_limits_for_tests


class FakeRedis:
    """Fixed-window counter stand-in with the two commands we use."""

    def __init__(self, *, fail: bool = False):
        self.counts: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail

    def incr(self, key: str) -> int:
        if self.fail:
            raise ConnectionError("redis down")
        self.counts[key] = self.counts.get(key, 0) + 1
        return self.counts[key]

    def expire(self, key: str, seconds: int) -> bool:
        if self.fail:
            raise ConnectionError("redis down")
        self.ttls[key] = seconds
        return True


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    rate_limit_redis.reset_for_tests()
    reset_rate_limits_for_tests()
    monkeypatch.setattr(rate_limit_redis.settings, "redis_url", "")
    yield
    rate_limit_redis.reset_for_tests()
    reset_rate_limits_for_tests()


def test_allows_hits_under_the_limit():
    fake = FakeRedis()
    rate_limit_redis.set_client_for_tests(fake)
    for _ in range(3):
        rate_limit_redis.check_rate_limit(
            "1.2.3.4", bucket="login", max_hits=3, window_seconds=60
        )
    assert fake.counts["ratelimit:login:1.2.3.4"] == 3
    assert fake.ttls["ratelimit:login:1.2.3.4"] == 60


def test_raises_429_with_detail_once_exceeded():
    fake = FakeRedis()
    rate_limit_redis.set_client_for_tests(fake)
    rate_limit_redis.check_rate_limit(
        "1.2.3.4", bucket="login", max_hits=1, window_seconds=60
    )
    with pytest.raises(HTTPException) as exc:
        rate_limit_redis.check_rate_limit(
            "1.2.3.4", bucket="login", max_hits=1, window_seconds=60, detail="Slow down"
        )
    assert exc.value.status_code == 429
    assert exc.value.detail == "Slow down"


def test_ttl_set_only_on_first_hit():
    fake = FakeRedis()
    rate_limit_redis.set_client_for_tests(fake)
    for _ in range(4):
        rate_limit_redis.check_rate_limit(
            "9.9.9.9", bucket="signup", max_hits=10, window_seconds=120
        )
    assert fake.ttls == {"ratelimit:signup:9.9.9.9": 120}


def test_keys_are_partitioned_by_bucket():
    fake = FakeRedis()
    rate_limit_redis.set_client_for_tests(fake)
    rate_limit_redis.check_rate_limit("ip", bucket="a", max_hits=1, window_seconds=60)
    # A different bucket for the same key must not be blocked.
    rate_limit_redis.check_rate_limit("ip", bucket="b", max_hits=1, window_seconds=60)
    assert set(fake.counts) == {"ratelimit:a:ip", "ratelimit:b:ip"}


def test_redis_failure_falls_back_to_in_process_limiter(monkeypatch):
    botocore_like = FakeRedis(fail=True)
    rate_limit_redis.set_client_for_tests(botocore_like)

    # Local limiter caps at one hit; the second must 429 locally, not from Redis.
    rate_limit_redis.check_rate_limit("ip", bucket="fallback", max_hits=1, window_seconds=60)
    with pytest.raises(HTTPException) as exc:
        rate_limit_redis.check_rate_limit("ip", bucket="fallback", max_hits=1, window_seconds=60)
    assert exc.value.status_code == 429


def test_no_redis_configured_uses_in_process_limiter():
    rate_limit_redis.set_client_for_tests(None)
    assert rate_limit_redis.backend_name() == "process"
    rate_limit_redis.check_rate_limit("ip", bucket="local", max_hits=1, window_seconds=60)
    with pytest.raises(HTTPException):
        rate_limit_redis.check_rate_limit("ip", bucket="local", max_hits=1, window_seconds=60)


def test_backend_name_reports_redis_when_injected():
    rate_limit_redis.set_client_for_tests(FakeRedis())
    assert rate_limit_redis.backend_name() == "redis"


def test_missing_redis_package_is_tolerated(monkeypatch):
    """An ImportError must disable Redis quietly rather than break requests."""
    monkeypatch.setattr(rate_limit_redis.settings, "redis_url", "redis://localhost:6379/0")
    rate_limit_redis.reset_for_tests()

    monkeypatch.setattr(rate_limit_redis, "_client_attempted", True, raising=False)
    monkeypatch.setattr(rate_limit_redis, "_client_disabled", True, raising=False)
    assert rate_limit_redis._get_client() is None

    rate_limit_redis.check_rate_limit("ip", bucket="no-pkg", max_hits=5, window_seconds=60)
