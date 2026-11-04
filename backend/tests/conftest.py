import os
import sys

# Ensure backend directory is in python path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Set test environment variables before importing app.config
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test_jobprep")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/15")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/14")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/13")
os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-chars-long-for-testing")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("COOKIE_SECURE", "false")
os.environ.setdefault("FRONTEND_URL", "http://localhost")

from typing import AsyncGenerator
import pytest
import fakeredis.aioredis
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel

from app.main import app
from app.config import settings
from app.core.database import get_session
from app.core.redis import get_redis_pool
from app.core.security import (
    create_access_token,
    create_refresh_token,
    new_token_family,
    get_password_hash,
)
from app.models.users import User
from app.models.job import Job
from app.models.news import NewsArticle
from app.models.url_seen import UrlSeen
from app.core.auth_cookies import ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE

TEST_SQLITE_URL = "sqlite+aiosqlite:///:memory:"


@pytest.fixture(scope="session")
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def fake_redis():
    """In-process mock Redis instance with full async API support."""
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    yield client
    await client.flushall()
    await client.aclose()


@pytest.fixture(autouse=True)
def patch_redis_and_limiter(fake_redis, monkeypatch):
    """Ensure all redis pool calls and slowapi limiter use in-memory fake redis."""
    from app.core.rate_limit import limiter

    limiter.enabled = False

    async def _mock_get_redis_pool():
        return fake_redis

    monkeypatch.setattr("app.core.redis.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.core.auth_cookies.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.core.google_oauth.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.api.v1.jobs.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.api.v1.stats.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.api.v1.search.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.api.v1.sse.get_redis_pool", _mock_get_redis_pool)
    monkeypatch.setattr("app.core.task_owner.get_redis_pool", _mock_get_redis_pool)


@pytest.fixture
async def mock_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Provides a fresh transactional database session using in-memory SQLite."""
    engine = create_async_engine(TEST_SQLITE_URL, echo=False)

    # In SQLite, remove postgresql-specific indexes for test table creation
    for table in SQLModel.metadata.tables.values():
        table.indexes = {
            idx
            for idx in table.indexes
            if not any(
                term in str(idx.name or "")
                for term in ["trgm", "ix_jobs_feed", "ix_jobs_scrape_status"]
            )
        }

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    SessionLocal = async_sessionmaker(
        engine, expire_on_commit=False, class_=AsyncSession
    )
    async with SessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
async def client(
    mock_db_session: AsyncSession, fake_redis
) -> AsyncGenerator[AsyncClient, None]:
    """FastAPI AsyncClient overriding DB and Redis dependencies."""
    app.dependency_overrides[get_session] = lambda: mock_db_session
    app.dependency_overrides[get_redis_pool] = lambda: fake_redis

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def test_user(mock_db_session: AsyncSession) -> User:
    """Creates and persists a standard test user."""
    user = User(
        email="testuser@example.com",
        hashed_password=get_password_hash("ValidPass123!"),
        full_name="Test User",
        is_active=True,
    )
    mock_db_session.add(user)
    await mock_db_session.commit()
    await mock_db_session.refresh(user)
    return user


@pytest.fixture
def auth_headers(test_user: User) -> dict:
    """Generates valid JWT auth cookies and CSRF tokens for authenticated tests."""
    fam = new_token_family()
    access, _, _ = create_access_token(test_user.email, family=fam)
    refresh, _, _ = create_refresh_token(test_user.email, family=fam)
    csrf = "test-csrf-token-secret-12345"

    return {
        "cookies": {
            ACCESS_COOKIE: access,
            REFRESH_COOKIE: refresh,
            CSRF_COOKIE: csrf,
        },
        "headers": {
            "X-CSRF-Token": csrf,
        },
    }
