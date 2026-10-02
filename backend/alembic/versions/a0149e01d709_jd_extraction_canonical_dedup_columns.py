"""jd extraction + canonical dedup columns

Revision ID: a0149e01d709
Revises: 52aec99ba09a
Create Date: 2026-09-18 15:40:21.125742

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                    # SQLModel emits sqlmodel.sql.sqltypes.AutoString
import pgvector.sqlalchemy         # pgvector emits pgvector.sqlalchemy.vector.VECTOR


# revision identifiers, used by Alembic.
revision: str = 'a0149e01d709'
down_revision: Union[str, Sequence[str], None] = '52aec99ba09a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


FK_CANONICAL = "fk_jobs_canonical_id_jobs"


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('canonical_hash', sqlmodel.sql.sqltypes.AutoString(length=64), nullable=True))
    op.add_column('jobs', sa.Column('canonical_id', sa.Uuid(), nullable=True))
    op.add_column('jobs', sa.Column('description_fetched_at', sa.DateTime(), nullable=True))
    op.create_index(op.f('ix_jobs_canonical_hash'), 'jobs', ['canonical_hash'], unique=False)
    op.create_index(op.f('ix_jobs_canonical_id'), 'jobs', ['canonical_id'], unique=False)
    # Named explicitly: autogenerate emitted `op.create_foreign_key(None, ...)`
    # and warned that the matching drop_constraint(None, ...) would fail.
    # ON DELETE SET NULL so removing a canonical row promotes its duplicates
    # instead of violating the constraint.
    op.create_foreign_key(
        FK_CANONICAL, 'jobs', 'jobs', ['canonical_id'], ['id'], ondelete='SET NULL'
    )

    # ── Read-path indexes ────────────────────────────────────────────────
    # The job feed is `WHERE is_active ORDER BY posted_at DESC NULLS LAST, id`.
    # Without this it was a full table scan + sort on every page request.
    # The trailing `id` matches the pagination tiebreaker, so offset paging is
    # deterministic and pages can't repeat or drop rows.
    op.execute(
        "CREATE INDEX ix_jobs_active_posted ON jobs "
        "(is_active, posted_at DESC NULLS LAST, id)"
    )
    # Backs the `scrape_status = 'raw'` claim query in process_raw_jobs_batch.
    op.execute(
        "CREATE INDEX ix_jobs_scrape_status ON jobs (scrape_status) "
        "WHERE scrape_status = 'raw'"
    )
    # pg_trgm is installed by the baseline migration but no index ever used
    # it, so the `q` filter's ILIKE '%...%' was a full scan.
    op.execute("CREATE INDEX ix_jobs_title_trgm ON jobs USING gin (title gin_trgm_ops)")
    op.execute("CREATE INDEX ix_jobs_company_trgm ON jobs USING gin (company gin_trgm_ops)")


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("DROP INDEX IF EXISTS ix_jobs_company_trgm")
    op.execute("DROP INDEX IF EXISTS ix_jobs_title_trgm")
    op.execute("DROP INDEX IF EXISTS ix_jobs_scrape_status")
    op.execute("DROP INDEX IF EXISTS ix_jobs_active_posted")
    op.drop_constraint(FK_CANONICAL, 'jobs', type_='foreignkey')
    op.drop_index(op.f('ix_jobs_canonical_id'), table_name='jobs')
    op.drop_index(op.f('ix_jobs_canonical_hash'), table_name='jobs')
    op.drop_column('jobs', 'description_fetched_at')
    op.drop_column('jobs', 'canonical_id')
    op.drop_column('jobs', 'canonical_hash')
