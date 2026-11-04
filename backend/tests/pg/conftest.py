"""
Fixtures for tests that need a real PostgreSQL (pgvector, pg_trgm, window
functions, ON CONFLICT, SKIP LOCKED) — SQL the in-memory SQLite fixture in
tests/conftest.py can't execute.

Point PG_TEST_URL at a database already migrated with `alembic upgrade head`
(CI's `backend-pg` job does this). Without it, every test here is skipped.
"""
import os
from typing import AsyncGenerator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine

PG_TEST_URL = os.environ.get("PG_TEST_URL")


def pytest_collection_modifyitems(config, items):
    if PG_TEST_URL:
        return
    skip = pytest.mark.skip(reason="PG_TEST_URL not set")
    for item in items:
        if "pg" in item.keywords:
            item.add_marker(skip)


@pytest.fixture
async def pg_engine() -> AsyncGenerator[AsyncEngine, None]:
    # One engine per test: pytest-asyncio gives each test its own event loop,
    # and asyncpg connections can't cross loops.
    engine = create_async_engine(PG_TEST_URL, echo=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def worker_db(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncEngine, None]:
    """For code that opens its own sessions (Celery task bodies use
    create_worker_session_ctx on settings.DATABASE_URL) and commits, so the
    rollback trick in pg_session can't contain it. Requires DATABASE_URL to
    point at the PG_TEST_URL database; empties the tables before and after.
    """
    from app.config import settings

    if settings.DATABASE_URL != PG_TEST_URL:
        pytest.skip("DATABASE_URL must equal PG_TEST_URL for worker-session tests")

    async def _truncate():
        async with pg_engine.begin() as conn:
            await conn.execute(text("TRUNCATE jobs, news_articles CASCADE"))

    await _truncate()
    try:
        yield pg_engine
    finally:
        await _truncate()


@pytest.fixture
async def pg_session(pg_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """A session inside an outer transaction that is always rolled back, so
    tests can commit freely without leaking rows into the next test."""
    async with pg_engine.connect() as conn:
        trans = await conn.begin()
        session = AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        )
        try:
            yield session
        finally:
            await session.close()
            await trans.rollback()
