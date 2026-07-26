from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlmodel import SQLModel
from app.config import settings

# Creates a connection pool to PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Celery-safe factory (creates a new engine per call) ──────────────────
def create_worker_session() -> async_sessionmaker[AsyncSession]:
    """
    Returns a NEW async_sessionmaker bound to a NEW engine.

    Celery workers use async_to_sync() which spawns a fresh event loop
    per task. Module-level engines get bound to the first loop and crash
    on subsequent tasks with 'another operation is in progress'. This
    factory avoids that by creating an isolated engine each time.
    """
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )
    return async_sessionmaker(
        worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )


async def get_session() -> AsyncSession:
    """
    FastAPI dependency: yields a database session and ensures cleanup.

    Usage in a route:
        @router.get("/jobs")
        async def list_jobs(session: AsyncSession = Depends(get_session)):
            ...

    The 'async with' block ensures the session is closed even if an
    exception occurs — like a try/finally block, but cleaner.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def create_all_tables():
    """
    Creates all tables defined in SQLModel models.
    Called once on app startup if tables don't exist.
    In production, use Alembic migrations instead.
    """
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)