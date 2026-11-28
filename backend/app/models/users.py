from typing import Optional, List
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON, Index, text
from datetime import datetime
from app.core.datetime_utils import utc_now


class User(SQLModel, table=True):
    __tablename__ = "users"
    __table_args__ = (
        # Case-insensitive uniqueness, and the index behind every sign-in
        # lookup (`lower(email) = ...` in auth._find_user_by_email).
        Index("ux_users_email_lower", text("lower(email)"), unique=True),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True)

    # Nullable: a Google-only account has no password.
    hashed_password: Optional[str] = Field(default=None)

    # Google's stable subject identifier.
    google_sub: Optional[str] = Field(default=None, unique=True, index=True)
    full_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)

    skills: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    is_active: bool = Field(default=True, nullable=False)
    is_admin: bool = Field(default=False, nullable=False)
    # Incrementing token_version invalidates all previously minted JWTs globally.
    token_version: int = Field(default=1, nullable=False)

    created_at: datetime = Field(default_factory=utc_now)
    last_login_at: Optional[datetime] = Field(default=None)
