"""
Public, aggregate-only board statistics for the marketing page.
"""
import json
import logging
from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from redis.exceptions import RedisError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.datetime_utils import utc_now
from app.core.rate_limit import limiter
from app.core.redis import get_cache_redis
from app.models.job import Job

logger = logging.getLogger(__name__)
router = APIRouter()

_CACHE_KEY = "public:stats"
_CACHE_SECONDS = 60


class PublicStatsResponse(BaseModel):
    active_jobs: int
    added_24h: int
    companies: int
    last_crawl_at: Optional[str] = None


@router.get("/", response_model=PublicStatsResponse)
@limiter.limit("60/minute")
async def public_stats(
    request: Request,
    response: Response,
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = f"public, max-age={_CACHE_SECONDS}"

    cache_redis = None
    try:
        cache_redis = await get_cache_redis()
        cached = await cache_redis.get(_CACHE_KEY)
        if cached:
            return json.loads(cached)
    except RedisError as exc:
        logger.warning("Stats cache read failed; falling back to database: %s", exc)

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
    if cache_redis is not None:
        try:
            await cache_redis.set(_CACHE_KEY, json.dumps(stats), ex=_CACHE_SECONDS)
        except RedisError as exc:
            logger.warning("Stats cache write failed: %s", exc)
    return stats
