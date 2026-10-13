from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel
import uuid

class NewsRead(BaseModel):
    id: uuid.UUID
    title: Optional[str] = None
    url: str
    source_domain: str
    published_at: Optional[datetime] = None
    scraped_at: datetime
    summary: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    # None while the AI summary is still queued; `summary` then holds the
    # page's own meta description.
    enriched_at: Optional[datetime] = None
    model_config = {"from_attributes": True}
