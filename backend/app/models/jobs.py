from datetime import datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, Dict
from sqlalchemy import UniqueConstraint, Column, JSON

class Company(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    domain: str = Field(unique=True, index=True, nullable=False) # e.g., stripe.com
    logo_url: Optional[str] = Field(default=None, nullable=True)
    size_range: Optional[str] = Field(default=None, nullable=True) # "1-10", "100-500", "1000+"
    industry: Optional[str] = Field(default=None, nullable=True)
    headquarter: Optional[str] = Field(default=None, nullable=True)
    description: Optional[str] = Field(default=None, nullable=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    jobs: List["Job"] = Relationship(back_populates="company")

class Job(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    company_id: UUID = Field(foreign_key="company.id", index=True)
    title_raw: str = Field(nullable=False)
    title_normalized: str = Field(index=True, nullable=False)
    seniority: str = Field(index=True, default="mid") # intern, junior, mid, senior, staff, principal, executive
    description_html: Optional[str] = Field(default=None, nullable=True)
    description_text: Optional[str] = Field(default=None, nullable=True)
    
    # JSON column for skills to support multi-dialect compatibility (SQlite/Postgres)
    skills_required: List[str] = Field(default=[], sa_column=Column(JSON))
    skills_preferred: List[str] = Field(default=[], sa_column=Column(JSON))
    
    salary_min_usd: Optional[int] = Field(default=None, nullable=True, index=True)
    salary_max_usd: Optional[int] = Field(default=None, nullable=True, index=True)
    salary_currency: Optional[str] = Field(default="USD", nullable=True)
    remote_policy: str = Field(index=True, default="onsite") # remote, hybrid, onsite
    location_city: Optional[str] = Field(default=None, nullable=True)
    location_country: Optional[str] = Field(default=None, nullable=True) # ISO 3166-1 alpha-2, e.g. US, DE
    visa_sponsorship: bool = Field(default=False)
    equity: bool = Field(default=False)
    apply_url: str = Field(nullable=False)
    content_fingerprint: str = Field(unique=True, index=True, nullable=False) # company + title_normalized + location
    quality_score: int = Field(default=0, index=True)
    
    # Store embedding as a JSON list of floats for compatibility across backends
    embedding: Optional[List[float]] = Field(sa_column=Column(JSON), default=None)
    
    is_active: bool = Field(default=True, index=True)
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = Field(default=None, nullable=True)
    
    source_urls: List[str] = Field(default=[], sa_column=Column(JSON))
    external_ids: Dict[str, str] = Field(default={}, sa_column=Column(JSON))
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    company: Company = Relationship(back_populates="jobs")
    applications: List["JobApplication"] = Relationship(back_populates="job")

class JobApplication(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("job_id", "user_id", name="unique_job_id_user_id"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id", index=True)
    job_id: UUID = Field(foreign_key="job.id", index=True)
    status: str = Field(default="Applied") # Saved, Applied, Interviewing, Rejected, Offer
    date_applied: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(default=None, nullable=True)

    user: "User" = Relationship(back_populates="jobs")
    job: Job = Relationship(back_populates="applications")

class CrawledURL(SQLModel, table=True):
    url_sha256: str = Field(primary_key=True, max_length=64)
    canonical_url: str = Field(nullable=False)
    source_id: Optional[UUID] = Field(default=None, nullable=True)
    first_seen_at: datetime = Field(default_factory=datetime.utcnow)
    last_seen_at: datetime = Field(default_factory=datetime.utcnow)
    http_status: Optional[int] = Field(default=None, nullable=True)
    content_hash: Optional[str] = Field(default=None, nullable=True, max_length=64)