from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List

from app.core.database import get_session
from app.models.news import NewsArticle
from app.models.users import User
from app.schemas.news import NewsRead
from app.tasks.news_tasks import crawl_news_site, scrape_linkedin_news
from app.api.v1.auth import get_current_user
from app.core.url_guard import UnsafeUrlError, validate_crawl_url

router = APIRouter()

@router.get("/", response_model=List[NewsRead])
async def list_news(
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(50)
    result = await session.execute(stmt)
    return result.scalars().all()

@router.post("/scrape")
async def trigger_news_scrape(
    url: str = Query(..., max_length=2048),
    current_user: User = Depends(get_current_user),
):
    """
    Queue a crawl of a user-supplied URL.

    The URL is validated against the SSRF guard first: this endpoint hands an
    arbitrary address to a worker inside the container network, so without it
    any authenticated user could reach cloud metadata (169.254.169.254),
    Postgres/Redis, or the unauthenticated Flower dashboard.
    """
    try:
        safe_url = validate_crawl_url(url)
    except UnsafeUrlError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    task = crawl_news_site.delay(safe_url)
    return {"status": "accepted", "task_id": task.id, "message": f"Crawling {safe_url}"}

@router.post("/scrape/linkedin")
async def trigger_linkedin_news(current_user: User = Depends(get_current_user)):
    """Trigger an on-demand LinkedIn News crawl"""
    task = scrape_linkedin_news.delay()
    return {"status": "accepted", "task_id": task.id, "message": "Fetching LinkedIn daily news"}