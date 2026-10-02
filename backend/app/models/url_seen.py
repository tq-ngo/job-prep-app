from datetime import datetime
from app.core.datetime_utils import utc_now
from typing import Optional
from sqlmodel import Field, SQLModel


class UrlSeen(SQLModel, table=True):
    """
    Permanent record of every URL the crawler has ever visited.

    Layer 3 of deduplication: durable across restarts, worker crashes,
    Redis evictions — this is the source of truth.
    """
    __tablename__ = "url_seen"
    url_sha256: str = Field(primary_key=True, max_length=64)
    canonical_url: str
    first_seen_at: datetime = Field(default_factory=utc_now)
    source_type: str