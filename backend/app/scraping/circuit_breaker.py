import time
import logging
from enum import Enum
from dataclasses import dataclass
from app.core.redis import create_worker_redis
from app.config import settings

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
    opened_at: float | None  # Unix timestamp when circuit opened


# How many consecutive failures before opening the circuit
FAILURE_THRESHOLD = 5
# How long (seconds) to keep circuit OPEN before testing
OPEN_DURATION_SECONDS = 90
# Redis key prefix
CB_PREFIX = "cb:v1"


class CircuitBreaker:
    """
    Redis-backed per-domain circuit breaker.
    
    All state lives in Redis so it's shared across all Celery workers.
    If one worker sees LinkedIn failing, all workers stop hitting LinkedIn.
    
    Usage:
        cb = CircuitBreaker()
        
        if not await cb.allow_request("linkedin.com"):
            logger.info("Circuit OPEN for linkedin.com — skipping")
            return
        
        try:
            response = await httpx_client.get(url)
            await cb.record_success("linkedin.com")
        except Exception:
            await cb.record_failure("linkedin.com")
            raise
    """
    
    async def get_status(self, domain: str) -> CircuitStatus:
        """Fetch current circuit state from Redis."""
        redis = create_worker_redis()
        
        # Pipeline: batch multiple Redis commands into one round-trip
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
        """
        Returns True if a request to this domain is allowed.
        
        Call this BEFORE making any HTTP request.
        """
        status = await self.get_status(domain)
        
        if status.state == CircuitState.CLOSED:
            return True
        
        if status.state == CircuitState.OPEN:
            # Check if enough time has passed to try again
            elapsed = time.time() - (status.opened_at or 0)
            if elapsed >= OPEN_DURATION_SECONDS:
                # Transition to HALF_OPEN to allow one test request
                await self._set_state(domain, CircuitState.HALF_OPEN)
                logger.info(f"Circuit HALF_OPEN for {domain} — testing")
                return True
            else:
                remaining = OPEN_DURATION_SECONDS - elapsed
                logger.info(f"Circuit OPEN for {domain} — {remaining:.0f}s remaining")
                return False
        
        if status.state == CircuitState.HALF_OPEN:
            # Only one test request allowed in HALF_OPEN
            # use Redis lock for atomicity
            return True
        
        return False
    
    async def record_success(self, domain: str):
        """
        Call this after a successful HTTP response.
        Resets failure count and closes the circuit.
        """
        redis = create_worker_redis()
        status = await self.get_status(domain)
        
        if status.state in (CircuitState.HALF_OPEN, CircuitState.OPEN):
            logger.info(f"Circuit CLOSED for {domain} — test succeeded")
        
        # Reset everything
        async with redis.pipeline(transaction=True) as pipe:
            pipe.delete(f"{CB_PREFIX}:{domain}:failures")
            pipe.delete(f"{CB_PREFIX}:{domain}:opened_at")
            pipe.set(f"{CB_PREFIX}:{domain}:state", CircuitState.CLOSED.value)
            await pipe.execute()
    
    async def record_failure(self, domain: str):
        """
        Call this after a failed HTTP request (timeout, 4xx, 5xx, etc.).
        Increments failure count; opens circuit if threshold reached.
        """
        redis = create_worker_redis()
        status = await self.get_status(domain)
        
        if status.state == CircuitState.HALF_OPEN:
            # Test failed — immediately re-open
            logger.warning(f"Circuit OPEN again for {domain} — test failed")
            await self._open_circuit(domain)
            return
        
        # Atomically increment failure counter
        failure_key = f"{CB_PREFIX}:{domain}:failures"
        new_count = await redis.incr(failure_key)
        # Set expiry so stale failures don't accumulate forever
        await redis.expire(failure_key, OPEN_DURATION_SECONDS * 10)
        
        logger.debug(f"Failure recorded for {domain}: {new_count}/{FAILURE_THRESHOLD}")
        
        if new_count >= FAILURE_THRESHOLD:
            logger.warning(f"Circuit OPEN for {domain} — {new_count} failures")
            await self._open_circuit(domain)
    
    async def _open_circuit(self, domain: str):
        redis = create_worker_redis()
        async with redis.pipeline(transaction=True) as pipe:
            pipe.set(f"{CB_PREFIX}:{domain}:state", CircuitState.OPEN.value)
            pipe.set(f"{CB_PREFIX}:{domain}:opened_at", str(time.time()))
            pipe.expire(f"{CB_PREFIX}:{domain}:state", OPEN_DURATION_SECONDS * 20)
            await pipe.execute()
    
    async def _set_state(self, domain: str, state: CircuitState):
        redis = create_worker_redis()
        await redis.set(f"{CB_PREFIX}:{domain}:state", state.value)


# Module-level singleton
circuit_breaker = CircuitBreaker()