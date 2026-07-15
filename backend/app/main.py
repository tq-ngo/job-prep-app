import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.core.database import create_all_tables
from app.scraping.playwright_scraper import playwright_scraper
from app.api.v1 import jobs, news, search, websocket, auth, tasks

import asyncio
import json
from app.core.redis import get_redis_pool
from app.api.v1.websocket import manager

logger = logging.getLogger(__name__)


async def redis_listener():
    """Background task to listen for job alerts on Redis and push to WebSockets."""
    redis = await get_redis_pool()
    pubsub = redis.pubsub()
    await pubsub.subscribe("new_jobs_channel")
    logger.info("Subscribed to Redis new_jobs_channel")
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                job_data = json.loads(message["data"])
                await manager.broadcast_new_job(job_data)
    except asyncio.CancelledError:
        logger.info("Redis listener cancelled")
    finally:
        await pubsub.unsubscribe("new_jobs_channel")

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
    
    # Start the Redis background listener
    listener_task = asyncio.create_task(redis_listener())
    
    logger.info("Startup complete")
    
    yield  # App runs here
    
    # ── SHUTDOWN ──────────────────────────────────────────────────────────
    logger.info("Shutting down...")
    listener_task.cancel()  # Clean up listener
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
    app.include_router(websocket.router, prefix="/ws", tags=["WebSocket"])
    app.include_router(tasks.router, prefix="/api/v1/tasks", tags=["Tasks"])
    
    @app.get("/health")
    async def health_check():
        """Kubernetes/Docker healthcheck endpoint."""
        return {"status": "ok"}
    
    return app


app = create_app()