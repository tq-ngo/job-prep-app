from datetime import datetime
from typing import Optional, List
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text, JSON, UniqueConstraint
from pgvector.sqlalchemy import Vector
import uuid


class Job(SQLModel, table=True):
    """
    A single job listing scraped from an external source.

    Design decisions:
    - id: UUID (not int) → avoids ID guessing attacks, works in distributed systems
    - embedding: 768-dim vector → text-embedding-004 output dimension
    - skills: JSON array → easier to query with PostgreSQL's JSON operators
    """
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_jobs_external_id_source"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    external_id: str = Field(index=True)
    source: str
    source_url: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = Field(default="USD", max_length=3)
    apply_url: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    skills: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    seniority_level: Optional[str] = None
    employment_type: Optional[str] = None
    is_remote: Optional[bool] = None
    terms: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(768)))
    posted_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    enriched_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
    scrape_status: str = Field(default="raw")