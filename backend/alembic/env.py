import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config
from sqlmodel import SQLModel
from alembic import context

from app.models.job import Job
from app.models.news import NewsArticle
from app.models.url_seen import UrlSeen
from app.models.users import User
from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

target_metadata = SQLModel.metadata  # Alembic diffs against this

def run_migrations_online():
    """
    Run migrations against the live database.
    Uses async engine because we're using asyncpg.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
    )

    async def do_run_migrations(connection):
        await connection.run_sync(context.configure, 
                                  connection=connection, 
                                  target_metadata=target_metadata)
        async with context.begin_transaction():
            await connection.run_sync(context.run_migrations)

    asyncio.run(do_run_migrations(connectable))