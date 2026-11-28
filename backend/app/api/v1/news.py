import asyncio
from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer
from sqlmodel import select

from app.api.v1.auth import get_current_user, require_csrf
from app.core.database import get_session
from app.core.datetime_utils import utc_today_start
from app.core.rate_limit import limiter
from app.core.task_owner import record_task_owner
from app.core.url_guard import UnsafeUrlError, validate_crawl_url
from app.models.news import NewsArticle
from app.models.users import User
from app.schemas.news import NewsRead
from app.tasks.news_tasks import crawl_news_site

router = APIRouter()


@router.get("/", response_model=List[NewsRead])
@limiter.limit("60/minute")
async def list_news(
    request: Request,
    response: Response,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0, le=1000),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """Return today's news articles only (older days are pruned)."""
    response.headers["Cache-Control"] = "private, no-store"
    stmt = (
        select(NewsArticle)
        .options(
            defer(NewsArticle.content_raw),
            defer(NewsArticle.content_clean),
            defer(NewsArticle.embedding),
        )
        .where(NewsArticle.scraped_at >= utc_today_start())
        .order_by(NewsArticle.published_at.desc().nulls_last(), NewsArticle.scraped_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await session.execute(stmt)
    return result.scalars().all()


@router.post("/scrape", status_code=202)
@limiter.limit("5/hour")
async def trigger_news_scrape(
    request: Request,
    url: str = Query(..., max_length=2048),
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
    """Queue a user-submitted article URL crawl after SSRF validation."""
    try:
        safe_url = await asyncio.to_thread(validate_crawl_url, url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task = await asyncio.to_thread(crawl_news_site.delay, safe_url)
    await record_task_owner([task.id], current_user.id)
    return {"status": "accepted", "task_id": task.id, "message": f"Crawling {safe_url}"}
