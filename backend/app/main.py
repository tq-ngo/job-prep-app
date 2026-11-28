import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy import text

from app.config import settings
from app.core.database import AsyncSessionLocal, assert_schema_current, engine
from app.core.locks import acquire_lock
from app.core.rate_limit import limiter
from app.ai.gemini_client import verify_model
from app.api.v1 import jobs, news, search, auth, tasks, sse, stats
from app.core.redis import close_redis_pool, get_redis_pool

logger = logging.getLogger(__name__)


async def _json_rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": f"Rate limit exceeded: {exc.detail}"},
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan: startup verification/bootstrap and graceful shutdown."""
    logger.info("Starting Job Prep Platform...")

    await assert_schema_current()
    await verify_model()

    # Automatically bootstrap initial postings and today's Google top news if empty,
    # guarded by Redis NX locks so concurrent replicas only enqueue once.
    try:
        from app.core.datetime_utils import utc_today_start
        from app.models.job import Job
        from app.models.news import NewsArticle
        from sqlmodel import select, func

        async with AsyncSessionLocal() as session:
            job_count = await session.scalar(select(func.count(Job.id)))
            today_news_count = await session.scalar(
                select(func.count(NewsArticle.id)).where(
                    NewsArticle.scraped_at >= utc_today_start()
                )
            )
        if job_count == 0:
            redis = await get_redis_pool()
            if await acquire_lock(redis, "bootstrap:initial_github_scrape", 300):
                logger.info("Jobs table is empty; enqueuing initial GitHub scrape bootstrap...")
                from app.tasks.job_tasks import scrape_github

                await asyncio.to_thread(scrape_github.delay)
        if today_news_count == 0:
            redis = await get_redis_pool()
            if await acquire_lock(redis, "bootstrap:daily_google_news", 300):
                logger.info("No news for today; enqueuing daily Google News bootstrap...")
                from app.tasks.news_tasks import scrape_google_news

                await asyncio.to_thread(scrape_google_news.delay)
    except Exception as exc:
        logger.warning("Could not check or enqueue startup scrape bootstrap: %s", exc)

    logger.info("Startup complete")

    yield

    logger.info("Shutting down...")
    await close_redis_pool()
    await engine.dispose()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    docs_enabled = not settings.is_production
    app = FastAPI(
        title="Job Prep Platform",
        version="1.0.0",
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )

    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _json_rate_limit_handler)
    app.add_middleware(SlowAPIMiddleware)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-CSRF-Token", "Last-Event-ID"],
    )

    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
    app.include_router(news.router, prefix="/api/v1/news", tags=["News"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
    app.include_router(sse.router, prefix="/api/v1/stream", tags=["SSE"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
    app.include_router(stats.router, prefix="/api/v1/stats", tags=["Stats"])

    @app.get("/health")
    async def health_check():
        """Liveness probe."""
        return {"status": "ok"}

    @app.get("/readyz")
    async def readiness_check():
        """Readiness probe verifying Postgres and Redis connectivity."""
        try:
            async with AsyncSessionLocal() as session:
                await session.execute(text("SELECT 1"))
            redis = await get_redis_pool()
            if not await redis.ping():
                raise RuntimeError("Redis ping returned false")
        except Exception as exc:
            logger.warning("Readiness check failed: %s", exc)
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return {"status": "ready"}

    return app


app = create_app()
