import asyncio
from logging.config import fileConfig
from sqlalchemy.ext.asyncio import async_engine_from_config, AsyncConnection
from sqlmodel import SQLModel
from alembic import context

from app.models.job import Job
from app.models.news import NewsArticle
from app.models.url_seen import UrlSeen
from app.models.users import User
from app.config import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = SQLModel.metadata  # Alembic diffs against this


def run_migrations_offline():
    """
    Run migrations in 'offline' mode — generates SQL script without
    connecting to the database.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """
    Run migrations against the live database.
    Uses async engine because we're using asyncpg.
    """
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
    )

    async def do_run_migrations():
        async with connectable.connect() as connection:
            await connection.run_sync(_configure_and_run)
        await connectable.dispose()

    def _configure_and_run(connection):
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()

    asyncio.run(do_run_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()