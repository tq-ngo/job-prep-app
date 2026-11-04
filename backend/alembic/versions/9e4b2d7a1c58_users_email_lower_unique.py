"""case-insensitive unique index on users.email

Revision ID: 9e4b2d7a1c58
Revises: 7c1d9e3f4a20
Create Date: 2026-11-03 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9e4b2d7a1c58'
down_revision: Union[str, Sequence[str], None] = '7c1d9e3f4a20'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Rows created before email normalization may differ only by case. The
    # index can't be built over them, and picking which account survives is
    # a human decision (they may hold different skills or a Google link), so
    # stop with the list instead of guessing.
    dupes = op.get_bind().execute(sa.text(
        "SELECT lower(email) AS email, array_agg(id ORDER BY id) AS ids"
        " FROM users GROUP BY lower(email) HAVING count(*) > 1"
    )).all()
    if dupes:
        listing = "; ".join(f"{row.email}: ids {list(row.ids)}" for row in dupes)
        raise RuntimeError(
            "Cannot create ux_users_email_lower: case-variant duplicate emails "
            f"exist ({listing}). Merge or delete the extras, then re-run."
        )

    op.create_index(
        'ux_users_email_lower',
        'users',
        [sa.text('lower(email)')],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ux_users_email_lower', table_name='users')
