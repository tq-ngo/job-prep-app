"""
Public, aggregate-only board statistics for the marketing page.

The landing page used to hard-code its numbers ("~125+ daily roles", a
counter starting at 128). This serves the real ones. It is unauthenticated,
so it returns counts only — never rows — and is cached and rate-limited.
"""
import json
from datetime import timedelta

from fastapi import APIRouter, Depends, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.datetime_utils import utc_now
from app.core.rate_limit import limiter
from app.core.redis import get_redis_pool
from app.models.job import Job

router = APIRouter()

_CACHE_KEY = "public:stats"
_CACHE_SECONDS = 60


@router.get("/")
@limiter.limit("60/minute")
async def public_stats(request: Request, session: AsyncSession = Depends(get_session)):
    redis = await get_redis_pool()
    cached = await redis.get(_CACHE_KEY)
    if cached:
        return json.loads(cached)

    visible = (Job.is_active == True, Job.canonical_id.is_(None))  # noqa: E712
    since = utc_now() - timedelta(hours=24)
    active, added_24h, last_crawl, companies = (
        await session.execute(
            select(
                func.count(Job.id),
                func.count(Job.id).filter(Job.first_seen_at >= since),
                func.max(Job.scraped_at),
                func.count(func.distinct(Job.company)),
            ).where(*visible)
        )
    ).one()

    stats = {
        "active_jobs": active or 0,
        "added_24h": added_24h or 0,
        "companies": companies or 0,
        "last_crawl_at": last_crawl.isoformat() if last_crawl else None,
    }
    await redis.set(_CACHE_KEY, json.dumps(stats), ex=_CACHE_SECONDS)
    return stats
