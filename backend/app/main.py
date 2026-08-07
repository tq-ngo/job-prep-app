import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import create_all_tables
from app.scraping.playwright_scraper import playwright_scraper
from app.api.v1 import jobs, news, search, auth, tasks, sse

import asyncio
import json
from app.core.redis import get_redis_pool
from app.core.redis import get_redis_pool

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
    
    # Create DB tables (in production, use Alembic instead)
    await create_all_tables()
    
    # Start Playwright browser (expensive — do once)
    await playwright_scraper.start()
    

    
    logger.info("Startup complete")
    
    yield  # App runs here
    
    # ── SHUTDOWN ──────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    await playwright_scraper.stop()
    logger.info("Shutdown complete")


def create_app() -> FastAPI:
    app = FastAPI(
        title="Job Prep Platform",
        version="1.0.0",
        docs_url="/docs",          # Swagger UI
        redoc_url="/redoc",        # ReDoc (alternative API docs)
        lifespan=lifespan,
    )
    
    # CORS: Allow the frontend to call the API
    # In production: replace "*" with your actual frontend domain
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS.split(","),
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