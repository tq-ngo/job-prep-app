from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from typing import Optional

from app.core.database import get_session
from app.models.job import Job
from app.schemas.job import JobListResponse
from app.ai.embedder import generate_embedding

router = APIRouter()

@router.get("/semantic", response_model=JobListResponse)
async def semantic_search(
    query_text: str = Query(..., description="E.g., 'A frontend job using React and Tailwind' or paste a resume snippet"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session)
):
    """
    Semantic Vector Search powered by pgvector.
    
    1. Embeds the user's search query using Gemini text-embedding-004.
    2. Uses pgvector's Cosine Distance (<=>) to find jobs with the closest embedding.
    """
    # 1. Embed the search query
    try:
        query_embedding = await generate_embedding(query_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate embedding: {e}")
        
    offset = (page - 1) * page_size
    
    # 2. Query Postgres using vector distance
    # The cosine_distance operator computes mathematical distance.
    # Smallest distance = most semantically similar.
    stmt = (
        select(Job)
        .where(Job.is_active == True)
        .where(Job.embedding != None)  # Only search jobs that have AI embeddings
        .order_by(Job.embedding.cosine_distance(query_embedding))
        .offset(offset)
        .limit(page_size)
    )
    
    # Get total count of enriched jobs for pagination metadata
    count_stmt = select(func.count(Job.id)).where(Job.is_active == True).where(Job.embedding != None)
    
    jobs_result = await session.execute(stmt)
    count_result = await session.execute(count_stmt)
    
    jobs = jobs_result.scalars().all()
    total = count_result.scalar() or 0
    
    return JobListResponse(
        items=jobs,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )
