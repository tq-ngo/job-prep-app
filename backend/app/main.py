import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

from app.config import settings
from app.core.database import assert_schema_current
from app.core.rate_limit import limiter
from app.ai.gemini_client import verify_model
from app.api.v1 import jobs, news, search, auth, tasks, sse
from app.core.redis import close_redis_pool

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan: code before `yield` runs on startup,
    code after `yield` runs on shutdown.
    
    This replaces the old @app.on_event("startup") pattern.
    """
    # ── STARTUP ──────────────────────────────────────────────────────────
    logger.info("Starting Job Prep Platform...")

    # Schema is owned by Alembic; `alembic upgrade head` runs in the
    # entrypoint before uvicorn. This only asserts it actually happened.
    await assert_schema_current()

    # Fail fast on a wrong/retired GEMINI_MODEL rather than 404ing on every
    # call while the pipeline reports success. No-ops without an API key.
    await verify_model()

    # NOTE: Playwright/Chromium was started here, costing ~300MB RSS on every
    # API replica, but PlaywrightScraper.fetch has no call sites. JD extraction
    # uses the HTTP path (TLSImpersonateScraper) instead. Removed.

    logger.info("Startup complete")

    yield  # App runs here

    # ── SHUTDOWN ──────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    await close_redis_pool()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Prep Platform",
        version="1.0.0",
        docs_url="/docs",          # Swagger UI
        redoc_url="/redoc",        # ReDoc (alternative API docs)
        lifespan=lifespan,
    )
    
    # Rate limiting (Redis-backed, shared across replicas).
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)

    # CORS: Allow the frontend to call the API
    # In production: replace "*" with your actual frontend domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Register routers
    app.include_router(auth.router, prefix="/api/v1/auth", tags=["Auth"])
    app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["Jobs"])
    app.include_router(news.router, prefix="/api/v1/news", tags=["News"])
    app.include_router(search.router, prefix="/api/v1/search", tags=["Search"])
    app.include_router(sse.router, prefix="/api/v1/stream", tags=["SSE"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
    
    @app.get("/health")
    async def health_check():
        """Kubernetes/Docker healthcheck endpoint."""
        return {"status": "ok"}
    
    return app


app = create_app()