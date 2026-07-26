from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import uuid

class JobCreate(BaseModel):
    external_id: str
    source: str
    source_url: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = None
    description: Optional[str] = None
    apply_url: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = "USD"
    is_remote: Optional[bool] = None
    posted_at: Optional[datetime] = None
    terms: Optional[List[str]] = None

class JobRead(BaseModel):
    id: uuid.UUID
    external_id: str
    source: str
    source_url: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = None
    apply_url: str
    description: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = "USD"
    skills: Optional[List[str]] = None
    seniority_level: Optional[str] = None
    employment_type: Optional[str] = None
    is_remote: Optional[bool] = None
    terms: Optional[List[str]]
    posted_at: Optional[datetime] = None
    scraped_at: datetime
    enriched_at: Optional[datetime] = None
    is_active: bool
    model_config = {"from_attributes": True}  # Allow construction from ORM objects

class JobListResponse(BaseModel):
    items: List[JobRead]
    total: int
    page: int
    page_size: int
    pages: int
