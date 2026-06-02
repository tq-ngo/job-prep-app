from sqlmodel import SQLModel, Field
from typing import Optional
from uuid import UUID, uuid4
from datetime import datetime

class CorporateNewsItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    title: str
    target_company: str = Field(index=True) # e.g., Google, Meta, Apple
    raw_content: str
    url: str = Field(unique=True)
    ai_summary: Optional[str] = None
    market_sentiment: Optional[str] = None # e.g., Expanding Hiring, Layoffs, Product Launch
    published_at: datetime
    processed_at: datetime = Field(default_factory=datetime.utcnow)