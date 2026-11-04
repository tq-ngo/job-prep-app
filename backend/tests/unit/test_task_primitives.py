import asyncio
import threading
from unittest.mock import patch

import pytest

from app.ai.gemini_client import GeminiConfigError, GeminiThrottled, acquire_gemini_slots
from app.config import settings
from app.core.locks import acquire_lock, release_lock
from app.tasks.job_tasks import _tasks_per_minute
from app.tasks.runtime import run_async


# ── Locks ───────────────────────────────────────────────────────────────

@pytest.mark.unit
async def test_lock_is_exclusive_and_released_by_owner(fake_redis):
    token = await acquire_lock(fake_redis, "scrape_lock:x", 60)
    assert token
    assert await acquire_lock(fake_redis, "scrape_lock:x", 60) is None

    assert await release_lock(fake_redis, "scrape_lock:x", token)
    assert await fake_redis.get("scrape_lock:x") is None


@pytest.mark.unit
async def test_expired_owner_cannot_release_successors_lock(fake_redis):
    stale = await acquire_lock(fake_redis, "scrape_lock:x", 60)
    # The first run overran its TTL; a second run now holds the lock.
    await fake_redis.delete("scrape_lock:x")
    current = await acquire_lock(fake_redis, "scrape_lock:x", 60)

    assert not await release_lock(fake_redis, "scrape_lock:x", stale)
    assert await fake_redis.get("scrape_lock:x") == current
    assert not await release_lock(fake_redis, "scrape_lock:x", None)


# ── Shared Gemini budget ────────────────────────────────────────────────

@pytest.fixture
def budget(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_REQUESTS_PER_MINUTE", 4)
    # Pin the clock mid-window so the test can't straddle a minute boundary.
    with patch("app.ai.gemini_client.time.time", return_value=6_000_030.0):
        yield


@pytest.mark.unit
async def test_budget_admits_up_to_limit_then_throttles(fake_redis, budget):
    await acquire_gemini_slots(fake_redis, 2)
    await acquire_gemini_slots(fake_redis, 2)
    with pytest.raises(GeminiThrottled) as exc:
        await acquire_gemini_slots(fake_redis, 1)
    assert exc.value.retry_after == 31  # to the end of the minute, +1s

    # The refused reservation was handed back, not left counted.
    assert int(await fake_redis.get("gemini:slots:100000")) == 4


@pytest.mark.unit
async def test_budget_refuses_an_operation_bigger_than_the_limit(fake_redis, budget):
    with pytest.raises(GeminiConfigError):
        await acquire_gemini_slots(fake_redis, 5)


@pytest.mark.unit
async def test_budget_zero_disables_limiting(fake_redis, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_REQUESTS_PER_MINUTE", 0)
    for _ in range(50):
        await acquire_gemini_slots(fake_redis, 2)
    assert await fake_redis.keys("gemini:slots:*") == []


# ── Rate parsing ────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize(
    "rate, per_minute",
    [("2/m", 2), ("30/h", 0.5), ("1/s", 60), ("5", 300), (" 4 / m ", 4), ("junk", 1)],
)
def test_tasks_per_minute(rate, per_minute):
    assert _tasks_per_minute(rate) == pytest.approx(per_minute)


# ── In-loop task timeout ────────────────────────────────────────────────

@pytest.mark.unit
def test_run_async_timeout_cancels_and_runs_finally():
    cleaned_up = threading.Event()

    async def hung_crawl():
        try:
            await asyncio.sleep(30)
        except Exception:
            # The tasks' `except Exception: self.retry(...)` handlers must not
            # see the timeout, or a hung crawl would be retried.
            pytest.fail("timeout was catchable as Exception")
        finally:
            cleaned_up.set()  # e.g. releasing the scrape lock

    with pytest.raises(TimeoutError):
        run_async(hung_crawl, timeout=0.05)
    assert cleaned_up.is_set()


@pytest.mark.unit
def test_run_async_passes_args_and_result():
    async def add(a, b):
        return a + b

    assert run_async(add, 2, 3) == 5
