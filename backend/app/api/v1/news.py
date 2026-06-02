from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.news import CorporateNewsItem
from app.services.ai_agent import GeminiAgentService
from typing import List

router = APIRouter()

@router.post("/ingest", response_model=CorporateNewsItem)
async def ingest_corporate_story(
    item: CorporateNewsItem, 
    session: AsyncSession = Depends(get_session)
):
    # Verify uniqueness of article entry to prevent redundant processing steps
    stmt = select(CorporateNewsItem).where(CorporateNewsItem.url == item.url)
    result = await session.execute(stmt)
    duplicate = result.scalars().first()

    if duplicate:
        raise HTTPException(status_code=400, detail="Article URL already exists inside index.")

    # Inject context validation into the synthesis logic pipeline using the async AI agent
    ai_service = GeminiAgentService()
    synthesis = await ai_service.synthesize_market_news(raw_content=item.raw_content)

    item.ai_summary = synthesis.summary
    item.market_sentiment = f"Sentiment: {synthesis.hiring_sentiment} | Impact: {synthesis.impact_level}"

    session.add(item)
    await session.commit()
    await session.refresh(item)
    return item

@router.get("/", response_model=List[CorporateNewsItem])
async def list_synthesized_news(session: AsyncSession = Depends(get_session)):
    stmt = select(CorporateNewsItem).order_by(CorporateNewsItem.published_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()