from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional

class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    email: str = Field(unique=True, index=True, nullable=False)
    hashed_password: str = Field(nullable=False)
    leetcode_username: Optional[str] = Field(default=None)

    jobs: List["JobApplication"] = Relationship(back_populates="user")
    leetcode_stats: List["LeetCodeSnapshot"] = Relationship(back_populates="user")
    leetcode_submissions: List["LeetCodeSubmission"] = Relationship(back_populates="user")