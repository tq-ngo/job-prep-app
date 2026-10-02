from typing import Optional, List
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON
from datetime import datetime
from app.core.datetime_utils import utc_now


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)

    # Nullable: a Google-only account has no password. Previously this was
    # NOT NULL, which made it impossible to represent an OAuth user at all.
    hashed_password: Optional[str] = Field(default=None)

    # Google's stable subject identifier. Preferred over email for lookup
    # because a Google account's email can change while `sub` never does.
    google_sub: Optional[str] = Field(default=None, unique=True, index=True)
    full_name: Optional[str] = Field(default=None)
    avatar_url: Optional[str] = Field(default=None)

    # `default=[]` was a MUTABLE DEFAULT shared across every instantiation;
    # default_factory gives each row its own list.
    skills: List[str] = Field(default_factory=list, sa_column=Column(JSON))

    # Lets an account be disabled without deleting it. There was previously
    # no way to revoke access to a user at all.
    is_active: bool = Field(default=True, nullable=False)

    created_at: datetime = Field(default_factory=utc_now)
    last_login_at: Optional[datetime] = Field(default=None)
