from datetime import datetime
from app.core.datetime_utils import utc_now
from typing import Optional, List
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import Text, JSON
from pgvector.sqlalchemy import Vector
import uuid


class NewsArticle(SQLModel, table=True):
    """
    A scraped news article. Similar structure to Job but for news content.
    """
    __tablename__ = "news_articles"
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    url: str = Field(unique=True, index=True)
    url_sha256: str = Field(max_length=64, index=True)
    title: Optional[str] = None
    author: Optional[str] = None
    published_at: Optional[datetime] = None
    content_raw: Optional[str] = Field(default=None, sa_column=Column(Text))
    content_clean: Optional[str] = Field(default=None, sa_column=Column(Text))
    summary: Optional[str] = Field(default=None, sa_column=Column(Text))
    categories: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    tags: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    source_domain: str = Field(index=True)
    crawl_depth: int = Field(default=0)
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(768)))
    scraped_at: datetime = Field(default_factory=utc_now)
    enriched_at: Optional[datetime] = None