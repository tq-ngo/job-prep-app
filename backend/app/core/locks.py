"""
Owner-checked Redis locks for Celery tasks.

The scrape locks stored the constant "locked" and were released with a bare
DEL. A run that outlived the lock's TTL therefore deleted the lock now held
by the NEXT run, letting a third run start alongside it. Each acquisition now
stores a random token, and release deletes the key only if it still holds
that token.
"""
import secrets
from typing import Optional

from redis.exceptions import WatchError


async def acquire_lock(redis, key: str, ttl_seconds: int) -> Optional[str]:
    """Take the lock; return its token, or None if someone else holds it."""
    token = secrets.token_hex(16)
    if await redis.set(key, token, nx=True, ex=ttl_seconds):
        return token
    return None


async def release_lock(redis, key: str, token: Optional[str]) -> bool:
    """Delete `key` only if it still holds `token`. True if released.

    GET-compare-DEL inside WATCH/MULTI, so a lock that expires and is
    re-acquired between the compare and the delete aborts the transaction
    instead of being deleted. (A Lua script would do the same in one round
    trip, but fakeredis can't run Lua without an extra native dependency.)
    """
    if not token:
        return False
    async with redis.pipeline(transaction=True) as pipe:
        try:
            await pipe.watch(key)
            if await pipe.get(key) != token:
                await pipe.unwatch()
                return False
            pipe.multi()
            pipe.delete(key)
            await pipe.execute()
            return True
        except WatchError:
            return False
