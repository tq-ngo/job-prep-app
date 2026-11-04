"""
Running a task's async body from Celery, with a time limit that works.

Celery's soft_time_limit is a signal raised in the worker's main thread.
async_to_sync runs the coroutine on a separate event-loop thread, so the
signal surfaced outside the coroutine: the task was reported failed while
the crawl kept running, and the coroutine's `finally` (which releases the
scrape lock) only ran whenever the crawl eventually ended.

asyncio.timeout cancels the coroutine itself, so its `finally` blocks run
at the deadline. CancelledError is a BaseException, so the tasks'
`except Exception: self.retry(...)` handlers don't turn a timeout into a
retry of a hung crawl. Each task also sets a Celery hard `time_limit` a
little above its timeout, as a backstop that kills the process.
"""
import asyncio
from typing import Any, Awaitable, Callable

from asgiref.sync import async_to_sync

# Default in-loop budget for a task body; celery_app sets the matching
# global hard limit (DEFAULT_TASK_TIMEOUT + HARD_LIMIT_GRACE).
DEFAULT_TASK_TIMEOUT = 300
# How long past its in-loop timeout a task may run before Celery kills it.
HARD_LIMIT_GRACE = 60


def run_async(
    fn: Callable[..., Awaitable[Any]], *args: Any, timeout: float = DEFAULT_TASK_TIMEOUT
) -> Any:
    async def _runner():
        async with asyncio.timeout(timeout):
            return await fn(*args)

    return async_to_sync(_runner)()
