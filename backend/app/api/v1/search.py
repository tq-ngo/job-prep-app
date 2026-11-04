import hashlib
import json
import logging

from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func

from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.core.redis import get_redis_pool
from app.models.job import Job
from app.models.users import User
from app.schemas.job import JobListResponse
from sqlalchemy.orm import defer
from app.ai.embedder import generate_embedding
from app.ai.gemini_client import GeminiTransientError
from app.api.v1.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# Query embeddings are deterministic, so a repeated search (or the next
# page of one) needn't spend another Gemini call. The free tier allows ~20
# requests a DAY, shared with job enrichment.
_EMBED_CACHE_PREFIX = "emb:q:"
_EMBED_CACHE_TTL = 24 * 3600


async def _query_embedding(query_text: str) -> list[float]:
    normalized = " ".join(query_text.lower().split())
    key = _EMBED_CACHE_PREFIX + hashlib.sha256(normalized.encode()).hexdigest()
    redis = await get_redis_pool()
    cached = await redis.get(key)
    if cached:
        return json.loads(cached)
    embedding = await generate_embedding(normalized, task_type="RETRIEVAL_QUERY")
    await redis.setex(key, _EMBED_CACHE_TTL, json.dumps(list(embedding)))
    return embedding


@router.get("/semantic", response_model=JobListResponse)
@limiter.limit("10/minute")
async def semantic_search(
    request: Request,
    query_text: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="E.g., 'A frontend job using React and Tailwind' or paste a resume snippet",
    ),
    page: int = Query(default=1, ge=1, le=20),
    page_size: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic Vector Search powered by pgvector.

    1. Embeds the user's search query using Gemini text-embedding-004.
    2. Uses pgvector's Cosine Distance (<=>) to find jobs with the closest embedding.
    """
    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Semantic search is not configured")

    # 1. Embed the search query. Failure details stay in the log: they used
    # to be echoed to the client, including SDK error text.
    try:
        query_embedding = await _query_embedding(query_text)
    except GeminiTransientError as exc:
        logger.warning("Query embedding throttled: %s", exc)
        headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
        raise HTTPException(
            status_code=503, detail="Semantic search is busy, try again shortly", headers=headers
        )
    except Exception:
        logger.exception("Query embedding failed")
        raise HTTPException(status_code=503, detail="Semantic search is unavailable")

    offset = (page - 1) * page_size

    # 2. Query Postgres using vector distance
    # The cosine_distance operator computes mathematical distance.
    # Smallest distance = most semantically similar.
    stmt = (
        select(Job)
        # JobListItem shows neither column; don't ship them out of Postgres.
        .options(defer(Job.embedding), defer(Job.description))
        .where(Job.is_active == True)
        .where(Job.canonical_id.is_(None))  # Collapse cross-source duplicates to canonical entity
        .where(Job.embedding != None)  # Only search jobs that have AI embeddings
        .order_by(Job.embedding.cosine_distance(query_embedding))
        .offset(offset)
        .limit(page_size)
    )

    # Get total count of enriched canonical jobs for pagination metadata
    count_stmt = (
        select(func.count(Job.id))
        .where(Job.is_active == True)
        .where(Job.canonical_id.is_(None))
        .where(Job.embedding != None)
    )

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
