from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, field_validator
import uuid

from app.core.datetime_utils import as_utc

from urllib.parse import urlparse

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

    @field_validator("apply_url")
    @classmethod
    def _validate_apply_url(cls, v: str) -> str:
        parsed = urlparse(v.strip())
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError(f"apply_url must use http or https scheme, got {parsed.scheme!r}")
        return v.strip()

    @field_validator("posted_at")
    @classmethod
    def _ensure_utc(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Normalize posted_at to aware UTC.

        Scraped dates arrive naive — LinkedIn sends an ISO date string that
        pydantic coerces without a timezone, GitHub's README dates come from
        strptime. The DB column is TIMESTAMPTZ and rejects naive values, so
        normalize once here rather than at each call site.
        """
        return as_utc(v)

class JobListItem(BaseModel):
    """
    A feed row. Deliberately has no `description`: list responses used to
    carry the full JD (up to 40k chars) for all 30 rows — approaching 1 MB a
    page, embedded a second time in the RSC payload — to show a table that
    never displays it. The drawer fetches JobRead by id instead.
    """
    id: uuid.UUID
    external_id: str
    source: str
    source_url: Optional[str] = None
    title: str
    company: str
    location: Optional[str] = None
    apply_url: str
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = "USD"
    salary_period: Optional[str] = None  # "hour" | "year"
    category: Optional[str] = None
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


class JobRead(JobListItem):
    """Full job, including the sanitized Markdown description."""
    description: Optional[str] = None


class JobListResponse(BaseModel):
    items: List[JobListItem]
    total: int
    page: int
    page_size: int
    pages: int
    # True when `total` was clamped to the UI cap, so the UI can show "500+"
    # instead of claiming exactly 500 roles exist.
    capped: bool = False
