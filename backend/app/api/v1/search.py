import hashlib
import json
import logging

from fastapi import APIRouter, Depends, Query, HTTPException, Request, Response
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import defer
from sqlmodel import select, func

from app.config import settings
from app.core.database import get_session
from app.core.rate_limit import limiter
from app.core.redis import get_cache_redis, get_redis_pool
from app.models.job import Job
from app.models.users import User
from app.schemas.job import JobListResponse
from app.api.v1.jobs import to_job_list_item
from app.ai.embedder import generate_embedding
from app.ai.gemini_client import GeminiTransientError, acquire_gemini_slots
from app.api.v1.auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

_EMBED_CACHE_PREFIX = "emb:q:"
_EMBED_CACHE_TTL = 24 * 3600
_MAX_SEMANTIC_PAGES = 20


def _normalize_query(query_text: str) -> str:
    return " ".join(query_text.lower().split())


async def _query_embedding(query_text: str) -> list[float]:
    normalized = _normalize_query(query_text)
    key = (
        f"{_EMBED_CACHE_PREFIX}{settings.EMBEDDING_MODEL}:"
        f"{hashlib.sha256(normalized.encode()).hexdigest()}"
    )
    cache_redis = None
    try:
        cache_redis = await get_cache_redis()
        cached = await cache_redis.get(key)
        if cached:
            return json.loads(cached)
    except RedisError as exc:
        logger.warning("Embedding cache read failed; continuing without cache: %s", exc)

    state_redis = await get_redis_pool()
    await acquire_gemini_slots(state_redis)
    embedding = await generate_embedding(normalized, task_type="RETRIEVAL_QUERY")

    if cache_redis is not None:
        try:
            await cache_redis.setex(key, _EMBED_CACHE_TTL, json.dumps(list(embedding)))
        except RedisError as exc:
            logger.warning("Embedding cache write failed: %s", exc)
    return embedding


@router.get("/semantic", response_model=JobListResponse)
@limiter.limit("10/minute")
async def semantic_search(
    request: Request,
    response: Response,
    query_text: str = Query(
        ...,
        min_length=2,
        max_length=200,
        description="E.g., 'A frontend job using React and Tailwind' or paste a resume snippet",
    ),
    page: int = Query(default=1, ge=1, le=_MAX_SEMANTIC_PAGES),
    page_size: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Semantic Vector Search powered by pgvector.
    """
    response.headers["Cache-Control"] = "private, no-store"

    normalized = _normalize_query(query_text)
    if len(normalized) < 2:
        raise HTTPException(
            status_code=422,
            detail="Query must contain at least 2 non-whitespace characters",
        )

    if not settings.GEMINI_API_KEY:
        raise HTTPException(status_code=503, detail="Semantic search is not configured")

    try:
        query_embedding = await _query_embedding(normalized)
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

    # Raise HNSW ef_search on Postgres for better recall with filtered + paged queries.
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        await session.execute(text("SET LOCAL hnsw.ef_search = 100"))

    stmt = (
        select(Job)
        .options(defer(Job.embedding), defer(Job.description))
        .where(Job.is_active == True)  # noqa: E712
        .where(Job.canonical_id.is_(None))
        .where(Job.embedding != None)  # noqa: E711
        .order_by(Job.embedding.cosine_distance(query_embedding))
        .offset(offset)
        .limit(page_size)
    )

    count_stmt = (
        select(func.count(Job.id))
        .where(Job.is_active == True)  # noqa: E712
        .where(Job.canonical_id.is_(None))
        .where(Job.embedding != None)  # noqa: E711
    )

    jobs_result = await session.execute(stmt)
    count_result = await session.execute(count_stmt)

    jobs = jobs_result.scalars().all()
    raw_total = count_result.scalar() or 0
    max_total = _MAX_SEMANTIC_PAGES * page_size
    total = min(raw_total, max_total)
    pages = max(1, (total + page_size - 1) // page_size) if total > 0 else 1
    items = [to_job_list_item(j) for j in jobs]

    return JobListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        capped=raw_total > max_total,
    )
