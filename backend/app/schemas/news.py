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
    summary: Optional[str] = None
    categories: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    model_config = {"from_attributes": True}
