"""dedup first_seen_at + queue queued_at

Revision ID: 5b8e2c71d0a4
Revises: c3f4373519e4
Create Date: 2026-10-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b8e2c71d0a4'
down_revision: Union[str, Sequence[str], None] = 'c3f4373519e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Added nullable, backfilled from scraped_at (the best available proxy for
    # first-seen on existing rows), then made NOT NULL.
    op.add_column('jobs', sa.Column('first_seen_at', sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE jobs SET first_seen_at = scraped_at")
    op.alter_column('jobs', 'first_seen_at', nullable=False)

    op.add_column('jobs', sa.Column('queued_at', sa.DateTime(timezone=True), nullable=True))
    # Rows already 'queued' get a fresh timestamp, so the reaper gives them
    # the normal grace period instead of requeueing them all at once.
    op.execute("UPDATE jobs SET queued_at = NOW() WHERE scrape_status = 'queued'")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'queued_at')
    op.drop_column('jobs', 'first_seen_at')
