"""add users is_admin/token_version, job check constraints, backfill sponsorship_label

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-11-27 21:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Atomic DDL + data backfill migration (no CONCURRENTLY statements)."""
    # 1. Users: RBAC admin flag + global token_version revocation counter
    op.add_column(
        "users",
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column(
        "users",
        sa.Column("token_version", sa.Integer(), nullable=False, server_default="1"),
    )
    # Remove redundant plain index on email (ux_users_email_lower + unique constraint suffice)
    op.execute("DROP INDEX IF EXISTS ix_users_email")

    # 2. Normalize any legacy/seeded invalid rows before enforcing CHECK constraints
    op.execute(
        "UPDATE jobs SET scrape_status = 'enriched' "
        "WHERE scrape_status NOT IN ('raw', 'queued', 'enriched', 'failed')"
    )
    op.execute(
        "UPDATE jobs SET canonical_id = NULL WHERE canonical_id = id"
    )
    op.execute(
        "UPDATE jobs SET salary_min = salary_max, salary_max = salary_min "
        "WHERE salary_min IS NOT NULL AND salary_max IS NOT NULL AND salary_min > salary_max"
    )
    # Backfill sponsorship_label for no_sponsorship rows left NULL by d4e5f6a7b8c9
    op.execute(
        "UPDATE jobs SET sponsorship_label = 'No Sponsorship' "
        "WHERE sponsorship_status = 'no_sponsorship' AND sponsorship_label IS NULL"
    )

    # 3. Job integrity CHECK constraints
    op.create_check_constraint(
        "ck_jobs_no_self_canonical",
        "jobs",
        "canonical_id IS NULL OR canonical_id <> id",
    )
    op.create_check_constraint(
        "ck_jobs_salary_range",
        "jobs",
        "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
    )
    op.create_check_constraint(
        "ck_jobs_scrape_status",
        "jobs",
        "scrape_status IN ('raw', 'queued', 'enriched', 'failed')",
    )


def downgrade() -> None:
    """Revert constraints and user columns."""
    op.drop_constraint("ck_jobs_scrape_status", "jobs", type_="check")
    op.drop_constraint("ck_jobs_salary_range", "jobs", type_="check")
    op.drop_constraint("ck_jobs_no_self_canonical", "jobs", type_="check")
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.drop_column("users", "token_version")
    op.drop_column("users", "is_admin")
