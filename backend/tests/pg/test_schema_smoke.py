import pytest
from sqlalchemy import text

from app.core import database

pytestmark = pytest.mark.pg


async def test_assert_schema_current_passes(pg_engine, monkeypatch):
    # Swap in the test engine so the startup guard runs on this test's loop.
    monkeypatch.setattr(database, "engine", pg_engine)
    await database.assert_schema_current()


async def test_required_extensions_installed(pg_session):
    rows = await pg_session.execute(
        text("SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_trgm')")
    )
    assert {r[0] for r in rows} == {"vector", "pg_trgm"}


async def test_cosine_distance_query_runs(pg_session):
    probe = "[" + ",".join(["0.1"] * 768) + "]"
    await pg_session.execute(
        text(
            "SELECT id FROM jobs WHERE embedding IS NOT NULL"
            " ORDER BY embedding <=> CAST(:v AS vector) LIMIT 1"
        ),
        {"v": probe},
    )
