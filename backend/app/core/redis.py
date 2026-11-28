from contextlib import asynccontextmanager
import redis.asyncio as aioredis
from app.config import settings

_DEFAULT_CONNECT_TIMEOUT = 2.0
_DEFAULT_SOCKET_TIMEOUT = 2.0
_HEALTH_CHECK_INTERVAL = 30


# ── Celery-safe factories (isolated client per call) ─────────────────────
def create_worker_redis() -> aioredis.Redis:
    """
    Creates an isolated state/queue Redis client for Celery workers.
    Each call returns a fresh client not tied to any prior event loop.
    """
    return aioredis.Redis.from_url(
        settings.REDIS_URL,
        max_connections=10,
        decode_responses=True,
        socket_connect_timeout=_DEFAULT_CONNECT_TIMEOUT,
        socket_timeout=_DEFAULT_SOCKET_TIMEOUT,
        health_check_interval=_HEALTH_CHECK_INTERVAL,
    )


def create_worker_cache_redis() -> aioredis.Redis:
    """
    Creates an isolated cache Redis client for Celery workers (evictable LRU).
    """
    return aioredis.Redis.from_url(
        settings.effective_redis_cache_url,
        max_connections=10,
        decode_responses=True,
        socket_connect_timeout=_DEFAULT_CONNECT_TIMEOUT,
        socket_timeout=_DEFAULT_SOCKET_TIMEOUT,
        health_check_interval=_HEALTH_CHECK_INTERVAL,
    )


def create_sse_redis(block_timeout_seconds: int = 30) -> aioredis.Redis:
    """
    Creates a dedicated Redis client for a long-lived SSE XREAD stream.
    Uses a socket_timeout comfortably above the XREAD block duration so
    blocking reads do not spuriously time out.
    """
    return aioredis.Redis.from_url(
        settings.REDIS_URL,
        max_connections=4,
        decode_responses=True,
        socket_connect_timeout=_DEFAULT_CONNECT_TIMEOUT,
        socket_timeout=block_timeout_seconds + 10,
        health_check_interval=_HEALTH_CHECK_INTERVAL,
    )


async def _close_client(client: aioredis.Redis) -> None:
    try:
        await client.aclose(close_connection_pool=True)
    except TypeError:
        await client.aclose()
        if hasattr(client, "connection_pool"):
            await client.connection_pool.disconnect()


@asynccontextmanager
async def worker_redis_ctx():
    """Async context manager for Celery workers (state/queue Redis)."""
    client = create_worker_redis()
    try:
        yield client
    finally:
        await _close_client(client)


@asynccontextmanager
async def worker_cache_redis_ctx():
    """Async context manager for Celery workers (evictable cache Redis)."""
    client = create_worker_cache_redis()
    try:
        yield client
    finally:
        await _close_client(client)


# ── FastAPI global pools (single event loop, safe) ───────────────────────
_pool: aioredis.ConnectionPool | None = None
_cache_pool: aioredis.ConnectionPool | None = None


async def get_redis_pool() -> aioredis.Redis:
    """Returns a Redis client backed by the state/queue connection pool."""
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=50,
            decode_responses=True,
            socket_connect_timeout=_DEFAULT_CONNECT_TIMEOUT,
            socket_timeout=_DEFAULT_SOCKET_TIMEOUT,
            health_check_interval=_HEALTH_CHECK_INTERVAL,
        )
    return aioredis.Redis(connection_pool=_pool)


async def get_cache_redis() -> aioredis.Redis:
    """
    Returns a Redis client backed by the evictable cache connection pool.
    Falls back to get_redis_pool() when REDIS_CACHE_URL is unset or identical
    to REDIS_URL (including test suites that monkeypatch get_redis_pool).
    """
    if not settings.REDIS_CACHE_URL.strip() or settings.REDIS_CACHE_URL.strip() == settings.REDIS_URL:
        return await get_redis_pool()
    global _cache_pool
    if _cache_pool is None:
        _cache_pool = aioredis.ConnectionPool.from_url(
            settings.effective_redis_cache_url,
            max_connections=50,
            decode_responses=True,
            socket_connect_timeout=_DEFAULT_CONNECT_TIMEOUT,
            socket_timeout=_DEFAULT_SOCKET_TIMEOUT,
            health_check_interval=_HEALTH_CHECK_INTERVAL,
        )
    return aioredis.Redis(connection_pool=_cache_pool)


async def close_redis_pool():
    """Called on app shutdown to cleanly close all Redis connection pools."""
    global _pool, _cache_pool
    if _pool:
        await _pool.disconnect()
        _pool = None
    if _cache_pool:
        await _cache_pool.disconnect()
        _cache_pool = None
