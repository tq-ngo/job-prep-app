"""job category, company_domain, salary_period, description_source + feed index

Revision ID: 7c1d9e3f4a20
Revises: 5b8e2c71d0a4
Create Date: 2026-10-05 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel                    # SQLModel emits sqlmodel.sql.sqltypes.AutoString


# revision identifiers, used by Alembic.
revision: str = '7c1d9e3f4a20'
down_revision: Union[str, Sequence[str], None] = '5b8e2c71d0a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Snapshot of app/scraping/categorize.py at the time of this migration:
# whole-word match on the normalized company / title. Migrations must not
# import app code, which keeps changing after the migration is written.
BACKFILL_CATEGORY = """UPDATE jobs SET category = CASE
        WHEN (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% meta %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% apple %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% amazon %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% netflix %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% google %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% microsoft %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% nvidia %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% tesla %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% tiktok %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% bytedance %' THEN 'FAANG+'
        WHEN (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% jane street %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% citadel %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% two sigma %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% hrt %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% hudson river trading %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% optiver %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% jump trading %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% akuna %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% drw %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% imc %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% tower research %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% point72 %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% de shaw %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% d e shaw %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% deshaw %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% renaissance technologies %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% susquehanna %' OR (' ' || btrim(regexp_replace(lower(company), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% sig %' OR (' ' || btrim(regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% quant %' OR (' ' || btrim(regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% quantitative %' OR (' ' || btrim(regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% algorithmic %' OR (' ' || btrim(regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% algo %' OR (' ' || btrim(regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% trading %' OR (' ' || btrim(regexp_replace(lower(title), '[^a-z0-9]+', ' ', 'g')) || ' ') LIKE '% hft %' THEN 'Quant'
        ELSE 'Others' END"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('category', sqlmodel.sql.sqltypes.AutoString(length=16), nullable=True))
    op.add_column('jobs', sa.Column('company_domain', sqlmodel.sql.sqltypes.AutoString(length=255), nullable=True))
    op.add_column('jobs', sa.Column('salary_period', sqlmodel.sql.sqltypes.AutoString(length=8), nullable=True))
    op.add_column('jobs', sa.Column('description_source', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True))
    op.execute(BACKFILL_CATEGORY)

    # CONCURRENTLY can't run inside a transaction, and the jobs table is read
    # constantly by the feed, so build the indexes without a write lock.
    with op.get_context().autocommit_block():
        op.execute("CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_category ON jobs (category)")
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_feed "
            "ON jobs (posted_at DESC NULLS LAST, id) "
            "WHERE is_active AND canonical_id IS NULL"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_active_posted")


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_active_posted "
            "ON jobs (is_active, posted_at DESC NULLS LAST, id)"
        )
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_feed")
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_category")
    op.drop_column('jobs', 'description_source')
    op.drop_column('jobs', 'salary_period')
    op.drop_column('jobs', 'company_domain')
    op.drop_column('jobs', 'category')
