from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
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
from contextlib import asynccontextmanager as _asynccontextmanager

def create_worker_session() -> async_sessionmaker[AsyncSession]:
    """
    Returns a NEW async_sessionmaker bound to a NEW engine.

    Celery workers use async_to_sync() which spawns a fresh event loop
    per task. Module-level engines get bound to the first loop and crash
    on subsequent tasks with 'another operation is in progress'. This
    factory avoids that by creating an isolated engine each time.

    IMPORTANT: Callers should use `create_worker_session_ctx()` instead
    when possible — it automatically disposes the engine on exit,
    preventing connection pool leaks.
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


@_asynccontextmanager
async def create_worker_session_ctx():
    """
    Context manager that yields a session and disposes the underlying
    engine on exit — preventing the connection pool leak that occurred
    when create_worker_session() was called without cleanup.

    Usage:
        async with create_worker_session_ctx() as session:
            ...  # session and engine are cleaned up automatically
    """
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        echo=False,
    )
    SessionLocal = async_sessionmaker(
        worker_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    try:
        async with SessionLocal() as session:
            yield session
    finally:
        await worker_engine.dispose()



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


async def assert_schema_current() -> None:
    """
    Verify the database is migrated to the latest Alembic revision.

    Replaces the old create_all_tables(). create_all() only ever CREATEs
    missing tables — it never ALTERs an existing one — so any column added
    to a model was silently absent at runtime. Schema is now owned entirely
    by Alembic (`alembic upgrade head`, run from the container entrypoint).

    This is a fail-fast guard, not a migrator: it refuses to serve traffic
    against a database whose revision doesn't match the migration head,
    which is what surfaces "forgot to migrate" as a startup error instead
    of a confusing UndefinedColumnError on the first request.
    """
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from sqlalchemy import text

    alembic_cfg = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    expected_heads = set(ScriptDirectory.from_config(alembic_cfg).get_heads())

    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                "SELECT version_num FROM alembic_version"
                " WHERE EXISTS (SELECT 1 FROM information_schema.tables"
                " WHERE table_name = 'alembic_version')"
            )
        )
        applied = {row[0] for row in result}

    if applied != expected_heads:
        raise RuntimeError(
            f"Database schema is out of date: applied={applied or '{}'} "
            f"expected={expected_heads}. Run `alembic upgrade head`."
        )