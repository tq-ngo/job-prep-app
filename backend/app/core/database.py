from contextlib import asynccontextmanager as _asynccontextmanager
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings


def _engine_kwargs(pool_size: int, max_overflow: int) -> dict:
    kwargs: dict = {
        "pool_size": pool_size,
        "max_overflow": max_overflow,
        "pool_pre_ping": True,
        "pool_recycle": 1800,
        "echo": False,
    }
    if settings.DATABASE_URL.startswith("postgresql+asyncpg"):
        kwargs["connect_args"] = {
            "command_timeout": 30,
            "server_settings": {
                "statement_timeout": "30000",
                "idle_in_transaction_session_timeout": "60000",
            },
        }
    return kwargs


# Creates a connection pool to PostgreSQL
engine = create_async_engine(
    settings.DATABASE_URL,
    **_engine_kwargs(pool_size=10, max_overflow=20),
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
    Callers should prefer `create_worker_session_ctx()` so the engine is
    disposed automatically on exit.
    """
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        **_engine_kwargs(pool_size=2, max_overflow=2),
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
    engine on exit. Uses a small pool (2 + 2 overflow) so API + Celery
    workers stay safely within PostgreSQL's connection budget.
    """
    worker_engine = create_async_engine(
        settings.DATABASE_URL,
        **_engine_kwargs(pool_size=2, max_overflow=2),
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
    Skips unnecessary COMMIT round-trips when no ORM objects were modified.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.new or session.dirty or session.deleted:
                await session.commit()
        except Exception:
            await session.rollback()
            raise


async def assert_schema_current() -> None:
    """Verify the database is migrated to the latest Alembic revision."""
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
