from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional

class JobApplication(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_name: str = Field(index=True)
    job_title: str = Field(index=True)
    job_url: str = Field(nullable=False)
    location: Optional[str] = Field(default=None, nullable=True)
    source: str  # e.g., "Simplify", "LinkedIn"
    status: str = Field(default="Applied")  # Saved, Applied, Interviewing, Rejected, Offer
    date_applied: datetime = Field(default_factory=datetime.utcnow)
    
    user_id: UUID = Field(foreign_key="user.id")
    user: "User" = Relationship(back_populates="jobs")