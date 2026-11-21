"""job sponsorship_status, sponsorship_label columns and b-tree index

Revision ID: d4e5f6a7b8c9
Revises: b3f8e1a6d2c9
Create Date: 2026-11-21 07:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, Sequence[str], None] = 'b3f8e1a6d2c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


BACKFILL_SPONSORSHIP = """UPDATE jobs SET
    sponsorship_status = CASE
        WHEN (title ~* '\\y(u\\.?s\\.?\\s+citizen(ship)?\\s+(required|only|status)|must be a u\\.?s\\.?\\s+citizen|u\\.?s\\.?\\s+person\\s+(required|only|status)|security clearance|active secret clearance|top secret|dod clearance|itar|export control laws?|export administration regulations?|requires? (u\\.?s\\.?\\s+)?citizenship|requires? (security\\s+)?clearance)\\y')
            OR (description IS NOT NULL AND description ~* '\\y(u\\.?s\\.?\\s+citizen(ship)?\\s+(required|only|status)|must be a u\\.?s\\.?\\s+citizen|u\\.?s\\.?\\s+person\\s+(required|only|status)|security clearance|active secret clearance|top secret|dod clearance|itar|export control laws?|export administration regulations?|requires? (u\\.?s\\.?\\s+)?citizenship|requires? (security\\s+)?clearance)\\y')
            THEN 'citizenship'
        WHEN (title ~* '\\y(will not sponsor|does not sponsor|no visa sponsorship|not eligible for (visa\\s+)?sponsorship|without (the\\s+)?need for (visa\\s+)?sponsorship|sponsorship (is\\s+)?not available|unable to (provide\\s+)?sponsor(ship)?|not able to sponsor)\\y')
            OR (description IS NOT NULL AND description ~* '\\y(will not sponsor|does not sponsor|no visa sponsorship|not eligible for (visa\\s+)?sponsorship|without (the\\s+)?need for (visa\\s+)?sponsorship|sponsorship (is\\s+)?not available|unable to (provide\\s+)?sponsor(ship)?|not able to sponsor)\\y')
            THEN 'no_sponsorship'
        WHEN (title ~* '\\y(visa sponsorship (is\\s+)?available|offers? (visa\\s+)?sponsorship|will sponsor (work\\s+)?visas?|provides? (visa\\s+)?sponsorship|sponsorship (is\\s+)?available for (eligible\\s+)?candidates|visa sponsorship provided|company(-|\\s+)sponsored visas?|h-?1b (sponsorship|sponsor|visa support|transfer)|sponsors? h-?1b|will sponsor h-?1b|offers? h-?1b|accepts?\\s+(cpt|opt)|(cpt|opt)\\s+accepted|cpt/opt\\s+eligible|eligible\\s+for\\s+(cpt|opt)|welcomes?\\s+cpt|welcomes?\\s+opt|welcomes?\\s+f-?1\\s+students?|f-?1\\s+visa\\s+sponsorship|cpt\\s+and\\s+opt\\s+students?\\s+welcome|cpt/opt\\s+sponsorship)\\y')
            OR (description IS NOT NULL AND description ~* '\\y(visa sponsorship (is\\s+)?available|offers? (visa\\s+)?sponsorship|will sponsor (work\\s+)?visas?|provides? (visa\\s+)?sponsorship|sponsorship (is\\s+)?available for (eligible\\s+)?candidates|visa sponsorship provided|company(-|\\s+)sponsored visas?|h-?1b (sponsorship|sponsor|visa support|transfer)|sponsors? h-?1b|will sponsor h-?1b|offers? h-?1b|accepts?\\s+(cpt|opt)|(cpt|opt)\\s+accepted|cpt/opt\\s+eligible|eligible\\s+for\\s+(cpt|opt)|welcomes?\\s+cpt|welcomes?\\s+opt|welcomes?\\s+f-?1\\s+students?|f-?1\\s+visa\\s+sponsorship|cpt\\s+and\\s+opt\\s+students?\\s+welcome|cpt/opt\\s+sponsorship)\\y')
            THEN 'sponsorship_available'
        ELSE NULL
    END,
    sponsorship_label = CASE
        WHEN (title ~* '\\y(u\\.?s\\.?\\s+citizen(ship)?\\s+(required|only|status)|must be a u\\.?s\\.?\\s+citizen|u\\.?s\\.?\\s+person\\s+(required|only|status)|security clearance|active secret clearance|top secret|dod clearance|itar|export control laws?|export administration regulations?|requires? (u\\.?s\\.?\\s+)?citizenship|requires? (security\\s+)?clearance)\\y')
            OR (description IS NOT NULL AND description ~* '\\y(u\\.?s\\.?\\s+citizen(ship)?\\s+(required|only|status)|must be a u\\.?s\\.?\\s+citizen|u\\.?s\\.?\\s+person\\s+(required|only|status)|security clearance|active secret clearance|top secret|dod clearance|itar|export control laws?|export administration regulations?|requires? (u\\.?s\\.?\\s+)?citizenship|requires? (security\\s+)?clearance)\\y')
            THEN 'US Citizen Required'
        WHEN (title ~* '\\y(will not sponsor|does not sponsor|no visa sponsorship|not eligible for (visa\\s+)?sponsorship|without (the\\s+)?need for (visa\\s+)?sponsorship|sponsorship (is\\s+)?not available|unable to (provide\\s+)?sponsor(ship)?|not able to sponsor)\\y')
            OR (description IS NOT NULL AND description ~* '\\y(will not sponsor|does not sponsor|no visa sponsorship|not eligible for (visa\\s+)?sponsorship|without (the\\s+)?need for (visa\\s+)?sponsorship|sponsorship (is\\s+)?not available|unable to (provide\\s+)?sponsor(ship)?|not able to sponsor)\\y')
            THEN NULL
        WHEN (title ~* '\\y(visa sponsorship (is\\s+)?available|offers? (visa\\s+)?sponsorship|will sponsor (work\\s+)?visas?|provides? (visa\\s+)?sponsorship|sponsorship (is\\s+)?available for (eligible\\s+)?candidates|visa sponsorship provided|company(-|\\s+)sponsored visas?|h-?1b (sponsorship|sponsor|visa support|transfer)|sponsors? h-?1b|will sponsor h-?1b|offers? h-?1b|accepts?\\s+(cpt|opt)|(cpt|opt)\\s+accepted|cpt/opt\\s+eligible|eligible\\s+for\\s+(cpt|opt)|welcomes?\\s+cpt|welcomes?\\s+opt|welcomes?\\s+f-?1\\s+students?|f-?1\\s+visa\\s+sponsorship|cpt\\s+and\\s+opt\\s+students?\\s+welcome|cpt/opt\\s+sponsorship)\\y')
            OR (description IS NOT NULL AND description ~* '\\y(visa sponsorship (is\\s+)?available|offers? (visa\\s+)?sponsorship|will sponsor (work\\s+)?visas?|provides? (visa\\s+)?sponsorship|sponsorship (is\\s+)?available for (eligible\\s+)?candidates|visa sponsorship provided|company(-|\\s+)sponsored visas?|h-?1b (sponsorship|sponsor|visa support|transfer)|sponsors? h-?1b|will sponsor h-?1b|offers? h-?1b|accepts?\\s+(cpt|opt)|(cpt|opt)\\s+accepted|cpt/opt\\s+eligible|eligible\\s+for\\s+(cpt|opt)|welcomes?\\s+cpt|welcomes?\\s+opt|welcomes?\\s+f-?1\\s+students?|f-?1\\s+visa\\s+sponsorship|cpt\\s+and\\s+opt\\s+students?\\s+welcome|cpt/opt\\s+sponsorship)\\y')
            THEN 'Sponsorship Available'
        ELSE NULL
    END"""


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('jobs', sa.Column('sponsorship_status', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True))
    op.add_column('jobs', sa.Column('sponsorship_label', sqlmodel.sql.sqltypes.AutoString(length=32), nullable=True))
    op.execute(BACKFILL_SPONSORSHIP)

    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_jobs_sponsorship_status "
            "ON jobs (sponsorship_status)"
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX CONCURRENTLY IF EXISTS ix_jobs_sponsorship_status")
    op.drop_column('jobs', 'sponsorship_label')
    op.drop_column('jobs', 'sponsorship_status')
