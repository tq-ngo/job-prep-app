import asyncio
import time
import logging
import weakref
from enum import Enum
from dataclasses import dataclass
from app.core.redis import create_worker_redis

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


@dataclass
class CircuitStatus:
    state: CircuitState
    domain: str
    failure_count: int
    opened_at: float | None


FAILURE_THRESHOLD = 5
OPEN_DURATION_SECONDS = 90
PROBE_TTL_SECONDS = 60
STATE_TTL_SECONDS = OPEN_DURATION_SECONDS * 20
CB_PREFIX = "cb:v1"


class CircuitBreaker:
    """Redis-backed per-domain circuit breaker."""

    def __init__(self):
        self._redis_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, object]" = (
            weakref.WeakKeyDictionary()
        )
        self._fallback_redis = None

    def _get_redis(self):
        """Return this event loop's Redis client, creating it on first use."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            if self._fallback_redis is None:
                self._fallback_redis = create_worker_redis()
            return self._fallback_redis

        client = self._redis_by_loop.get(loop)
        if client is None:
            client = create_worker_redis()
            self._redis_by_loop[loop] = client
        return client

    async def get_status(self, domain: str) -> CircuitStatus:
        """Fetch current circuit state from Redis."""
        redis = self._get_redis()
        async with redis.pipeline(transaction=False) as pipe:
            pipe.get(f"{CB_PREFIX}:{domain}:state")
            pipe.get(f"{CB_PREFIX}:{domain}:failures")
            pipe.get(f"{CB_PREFIX}:{domain}:opened_at")
            state_val, failures_val, opened_at_val = await pipe.execute()

        state = CircuitState(state_val) if state_val else CircuitState.CLOSED
        failures = int(failures_val) if failures_val else 0
        opened_at = float(opened_at_val) if opened_at_val else None

        return CircuitStatus(
            state=state,
            domain=domain,
            failure_count=failures,
            opened_at=opened_at,
        )

    async def allow_request(self, domain: str) -> bool:
        """Returns True if a request to this domain is allowed."""
        status = await self.get_status(domain)

        if status.state == CircuitState.CLOSED:
            return True

        if status.state == CircuitState.OPEN:
            elapsed = time.time() - (status.opened_at or 0)
            if elapsed >= OPEN_DURATION_SECONDS:
                await self._set_state(domain, CircuitState.HALF_OPEN)
                logger.info("Circuit HALF_OPEN for %s — testing", domain)
                return await self._claim_probe(domain)
            remaining = OPEN_DURATION_SECONDS - elapsed
            logger.info("Circuit OPEN for %s — %.0fs remaining", domain, remaining)
            return False

        if status.state == CircuitState.HALF_OPEN:
            return await self._claim_probe(domain)

        return False

    async def _claim_probe(self, domain: str) -> bool:
        redis = self._get_redis()
        return bool(
            await redis.set(f"{CB_PREFIX}:{domain}:probe", "1", nx=True, ex=PROBE_TTL_SECONDS)
        )

    async def record_success(self, domain: str):
        """Reset failure count and remove breaker keys (absent state == CLOSED)."""
        redis = self._get_redis()
        status = await self.get_status(domain)

        if status.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            logger.info("Circuit CLOSED for %s — test succeeded", domain)

        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(f"{CB_PREFIX}:{domain}:failures")
            pipe.delete(f"{CB_PREFIX}:{domain}:opened_at")
            pipe.delete(f"{CB_PREFIX}:{domain}:probe")
            pipe.delete(f"{CB_PREFIX}:{domain}:state")
            await pipe.execute()

    async def record_failure(self, domain: str):
        """Increment failure count; open circuit if threshold reached."""
        redis = self._get_redis()
        status = await self.get_status(domain)

        if status.state == CircuitState.HALF_OPEN:
            logger.warning("Circuit OPEN again for %s — test failed", domain)
            await self._open_circuit(domain)
            return

        failure_key = f"{CB_PREFIX}:{domain}:failures"
        new_count = await redis.incr(failure_key)
        await redis.expire(failure_key, OPEN_DURATION_SECONDS * 10)

        logger.debug("Failure recorded for %s: %d/%d", domain, new_count, FAILURE_THRESHOLD)

        if new_count >= FAILURE_THRESHOLD:
            logger.warning("Circuit OPEN for %s — %d failures", domain, new_count)
            await self._open_circuit(domain)

    async def _open_circuit(self, domain: str):
        redis = self._get_redis()
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(f"{CB_PREFIX}:{domain}:state", CircuitState.OPEN.value, ex=STATE_TTL_SECONDS)
            pipe.set(f"{CB_PREFIX}:{domain}:opened_at", str(time.time()), ex=STATE_TTL_SECONDS)
            pipe.delete(f"{CB_PREFIX}:{domain}:probe")
            await pipe.execute()

    async def _set_state(self, domain: str, state: CircuitState):
        redis = self._get_redis()
        await redis.set(f"{CB_PREFIX}:{domain}:state", state.value, ex=STATE_TTL_SECONDS)


circuit_breaker = CircuitBreaker()
