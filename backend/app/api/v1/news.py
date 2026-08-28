from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List

from app.core.database import get_session
from app.models.news import NewsArticle
from app.models.users import User
from app.schemas.news import NewsRead
from app.tasks.news_tasks import crawl_news_site, scrape_linkedin_news
from app.api.v1.auth import get_current_user

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
async def trigger_news_scrape(url: str, current_user: User = Depends(get_current_user)):
    task = crawl_news_site.delay(url)
    return {"status": "accepted", "task_id": task.id, "message": f"Crawling {url}"}

@router.post("/scrape/linkedin")
async def trigger_linkedin_news(current_user: User = Depends(get_current_user)):
    """Trigger an on-demand LinkedIn News crawl"""
    task = scrape_linkedin_news.delay()
    return {"status": "accepted", "task_id": task.id, "message": "Fetching LinkedIn daily news"}