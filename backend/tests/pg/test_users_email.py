import pytest
from sqlalchemy.exc import IntegrityError

from app.models.users import User

pytestmark = pytest.mark.pg


async def test_email_uniqueness_ignores_case(pg_session):
    pg_session.add(User(email="Case@Example.com", skills=[]))
    await pg_session.commit()

    pg_session.add(User(email="case@example.com", skills=[]))
    with pytest.raises(IntegrityError, match="ux_users_email_lower"):
        await pg_session.commit()
