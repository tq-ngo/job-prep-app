from datetime import datetime
from app.core.datetime_utils import utc_now
from typing import Optional, List
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import (
    JSON,
    ForeignKey,
    Index,
    Text,
    UniqueConstraint,
    Uuid,
    text,
)
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
    # Indexes are declared HERE, not only in the migration, so that
    # `alembic check` stays meaningful: raw-SQL-only indexes are invisible to
    # the model metadata, and the next --autogenerate would emit DROP INDEX
    # for them.
    __table_args__ = (
        UniqueConstraint("external_id", "source", name="uq_jobs_external_id_source"),
        # The job feed: WHERE is_active ORDER BY posted_at DESC NULLS LAST, id.
        # Trailing `id` matches the pagination tiebreaker so offset paging is
        # deterministic (pages can't repeat or drop rows).
        Index(
            "ix_jobs_active_posted",
            "is_active",
            text("posted_at DESC NULLS LAST"),
            "id",
        ),
        # Backs the scrape_status='raw' claim query in process_raw_jobs_batch.
        Index(
            "ix_jobs_scrape_status",
            "scrape_status",
            postgresql_where=text("scrape_status = 'raw'"),
        ),
        # pg_trgm is installed by the baseline migration but nothing used it,
        # so the `q` filter's ILIKE '%...%' was a full table scan.
        Index(
            "ix_jobs_title_trgm",
            "title",
            postgresql_using="gin",
            postgresql_ops={"title": "gin_trgm_ops"},
        ),
        Index(
            "ix_jobs_company_trgm",
            "company",
            postgresql_using="gin",
            postgresql_ops={"company": "gin_trgm_ops"},
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    external_id: str = Field(index=True)
    source: str
    source_url: Optional[str] = None

    # ── Cross-source deduplication (see scraping/db_sync.py) ─────────────
    # SHA-256 of normalized company|title|location. Previously this lived
    # ONLY in a TTL-less Redis set and a match caused the incoming job to be
    # silently DISCARDED — so e.g. 40 distinct Amazon "SWE Intern / Seattle"
    # reqs collapsed to one row, permanently and unrecoverably. It is now a
    # durable indexed column, and duplicates are LINKED rather than dropped.
    canonical_hash: Optional[str] = Field(default=None, max_length=64, index=True)
    # Points at the first job seen with this canonical_hash. NULL means "this
    # row is itself the canonical one", so the feed filters on
    # `canonical_id IS NULL` to collapse duplicates without losing rows.
    # Declared via sa_column so the constraint carries an explicit name and
    # ON DELETE SET NULL. SQLModel's `foreign_key=` shorthand emits an unnamed
    # constraint, which autogenerate warned would break `drop_constraint`.
    # SET NULL promotes duplicates when a canonical row is deleted.
    canonical_id: Optional[uuid.UUID] = Field(
        default=None,
        sa_column=Column(
            Uuid(),
            ForeignKey("jobs.id", name="fk_jobs_canonical_id_jobs", ondelete="SET NULL"),
            nullable=True,
            index=True,
        ),
    )
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
    scraped_at: datetime = Field(default_factory=utc_now)
    enriched_at: Optional[datetime] = None
    # Set when jd_extractor successfully populated `description`. Lets the
    # backfill task target rows that predate JD extraction, and distinguishes
    # "never attempted" from "attempted and unavailable".
    description_fetched_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
    scrape_status: str = Field(default="raw")