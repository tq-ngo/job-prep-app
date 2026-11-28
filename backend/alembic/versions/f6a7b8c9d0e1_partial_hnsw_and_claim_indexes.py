"""rebuild partial HNSW embedding index and active-canonical claim index

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-11-27 21:36:00.000000

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, Sequence[str], None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Isolated CONCURRENTLY index rebuild migration."""
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_embedding_hnsw")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_embedding_hnsw "
            "ON jobs USING hnsw (embedding vector_cosine_ops) "
            "WHERE is_active AND canonical_id IS NULL AND embedding IS NOT NULL"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_scrape_status")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_scrape_status "
            "ON jobs (first_seen_at DESC) "
            "WHERE scrape_status = 'raw' AND is_active AND canonical_id IS NULL"
        )


def downgrade() -> None:
    """Restore previous unfiltered HNSW and scrape_status indexes."""
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_scrape_status")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_scrape_status "
            "ON jobs (scrape_status) WHERE scrape_status = 'raw'"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_embedding_hnsw")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_embedding_hnsw "
            "ON jobs USING hnsw (embedding vector_cosine_ops)"
        )
