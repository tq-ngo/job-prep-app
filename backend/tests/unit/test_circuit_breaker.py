import pytest
import time

from app.scraping.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    FAILURE_THRESHOLD,
    OPEN_DURATION_SECONDS,
)


@pytest.mark.unit
async def test_circuit_breaker_transitions(fake_redis):
    cb = CircuitBreaker()
    # Direct breaker to our in-memory fake redis
    cb._get_redis = lambda: fake_redis

    domain = "test-target.com"

    # Initially CLOSED
    assert await cb.allow_request(domain) is True
    status = await cb.get_status(domain)
    assert status.state == CircuitState.CLOSED
    assert status.failure_count == 0

    # Record failures up to threshold - 1
    for i in range(FAILURE_THRESHOLD - 1):
        await cb.record_failure(domain)
        assert await cb.allow_request(domain) is True

    # Next failure hits threshold -> transitions to OPEN
    await cb.record_failure(domain)
    status = await cb.get_status(domain)
    assert status.state == CircuitState.OPEN
    assert await cb.allow_request(domain) is False

    # Simulate expiration of OPEN_DURATION_SECONDS by adjusting the opened_at key in redis
    await fake_redis.set(
        f"cb:v1:{domain}:opened_at", str(time.time() - (OPEN_DURATION_SECONDS + 10))
    )

    # Calling allow_request detects elapsed timeout and transitions to HALF_OPEN
    assert await cb.allow_request(domain) is True
    status = await cb.get_status(domain)
    assert status.state == CircuitState.HALF_OPEN

    # Record success -> transitions back to CLOSED
    await cb.record_success(domain)
    status = await cb.get_status(domain)
    assert status.state == CircuitState.CLOSED
    assert status.failure_count == 0
    assert await cb.allow_request(domain) is True
