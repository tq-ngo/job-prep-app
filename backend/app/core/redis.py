import redis.asyncio as aioredis
from app.config import settings

# Connection pool: reuse connections instead of creating new ones per request
# max_connections=50: Maximum simultaneous Redis connections
_pool: aioredis.ConnectionPool | None = None


async def get_redis_pool() -> aioredis.Redis:
    """
    Returns a Redis client backed by a connection pool.

    Why a pool? Creating a TCP connection is expensive (multiple round trips).
    A pool keeps connections alive and reuses them across requests.
    Think of it like a pool of taxis — you hail one, use it, return it.
    """
    global _pool
    if _pool is None:
        _pool = aioredis.ConnectionPool.from_url(
            settings.REDIS_URL,
            max_connections=50,
            decode_responses=True,
        )
    return aioredis.Redis(connection_pool=_pool)


async def close_redis_pool():
    """Called on app shutdown to cleanly close all connections."""
    global _pool
    if _pool:
        await _pool.disconnect()
        _pool = None