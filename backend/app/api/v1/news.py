from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from typing import List

from app.core.database import get_session
from app.models.news import NewsArticle
from app.schemas.news import NewsRead
from app.tasks.news_tasks import crawl_news_site

router = APIRouter()

@router.get("/", response_model=List[NewsRead])
async def list_news(session: AsyncSession = Depends(get_session)):
    stmt = select(NewsArticle).order_by(NewsArticle.published_at.desc()).limit(50)
    result = await session.execute(stmt)
    return result.scalars().all()

@router.post("/scrape")
async def trigger_news_scrape(url: str):
    task = crawl_news_site.delay(url)
    return {"status": "accepted", "task_id": task.id, "message": f"Crawling {url}"}