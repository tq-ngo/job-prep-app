"""
Who started which Celery task.

GET /api/v1/tasks/{id} used to return any task's result or error text to any
signed-in user who had (or guessed) its ID. The scrape endpoints now record
the caller as the owner, and the status endpoint answers only the owner.
"""
from typing import Iterable

from app.core.redis import get_redis_pool

_PREFIX = "task:owner:"
# Comfortably longer than any scrape, and than the result backend keeps
# results, so polling never outlives the record.
_TTL_SECONDS = 24 * 3600


async def record_task_owner(task_ids: Iterable[str], user_id: int) -> None:
    redis = await get_redis_pool()
    async with redis.pipeline(transaction=False) as pipe:
        for task_id in task_ids:
            pipe.setex(f"{_PREFIX}{task_id}", _TTL_SECONDS, str(user_id))
        await pipe.execute()


async def owns_all(task_ids: Iterable[str], user_id: int) -> bool:
    ids = list(task_ids)
    if not ids:
        return False
    redis = await get_redis_pool()
    owners = await redis.mget([f"{_PREFIX}{task_id}" for task_id in ids])
    expected = str(user_id)
    return all(
        (o.decode() if isinstance(o, bytes) else o) == expected for o in owners
    )
