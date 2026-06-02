from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, create_engine as sqlmodel_create_engine
from typing import AsyncGenerator
from app.core.config import settings

# CRITICAL: Database URL must use the postgresql+asyncpg:// driver prefix for async
ASYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql://", "postgresql+asyncpg://")
SYNC_DATABASE_URL = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")

async_engine = create_async_engine(
    ASYNC_DATABASE_URL,
    echo=False,
    pool_pre_ping=True
)

# Synchronous engine for Celery tasks
sync_engine = sqlmodel_create_engine(SYNC_DATABASE_URL, echo=False)

# Create a session maker bound to the async engine
async_session_maker = sessionmaker(
    async_engine, 
    class_=AsyncSession, 
    expire_on_commit=False
)

async def init_db() -> None:
    # SQLModel metadata generation requires running within an async engine context
    async with async_engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_maker() as session:
        yield session