"""hnsw embedding index, queued-jobs index, news published_at index

Revision ID: b3f8e1a6d2c9
Revises: 9e4b2d7a1c58
Create Date: 2026-11-04 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'b3f8e1a6d2c9'
down_revision: Union[str, Sequence[str], None] = '9e4b2d7a1c58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # CONCURRENTLY: jobs is read constantly by the feed and written by every
    # crawl, and an HNSW build over the existing vectors takes a while.
    # IF NOT EXISTS makes a re-run after a partial failure safe — each
    # statement commits on its own inside the autocommit block.
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_embedding_hnsw "
            "ON jobs USING hnsw (embedding vector_cosine_ops)"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_queued "
            "ON jobs (queued_at) WHERE scrape_status = 'queued'"
        )
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_news_articles_published_at "
            "ON news_articles (published_at DESC NULLS LAST)"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_news_articles_published_at")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_queued")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_embedding_hnsw")
