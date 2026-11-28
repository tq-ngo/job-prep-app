from datetime import datetime
from app.core.datetime_utils import utc_now
from typing import Optional, List
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import (
    CheckConstraint,
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
        CheckConstraint(
            "canonical_id IS NULL OR canonical_id <> id",
            name="ck_jobs_no_self_canonical",
        ),
        CheckConstraint(
            "salary_min IS NULL OR salary_max IS NULL OR salary_min <= salary_max",
            name="ck_jobs_salary_range",
        ),
        CheckConstraint(
            "scrape_status IN ('raw', 'queued', 'enriched', 'failed')",
            name="ck_jobs_scrape_status",
        ),
        # The job feed: WHERE is_active AND canonical_id IS NULL
        # ORDER BY posted_at DESC NULLS LAST, id.
        Index(
            "ix_jobs_feed",
            text("posted_at DESC NULLS LAST"),
            "id",
            postgresql_where=text("is_active AND canonical_id IS NULL"),
        ),
        # Backs the active-canonical newest-first claim query in process_raw_jobs_batch.
        Index(
            "ix_jobs_scrape_status",
            text("first_seen_at DESC"),
            postgresql_where=text("scrape_status = 'raw' AND is_active AND canonical_id IS NULL"),
        ),
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
        # Partial HNSW index over only feed-visible embedded rows so post-filtering
        # never degrades recall or wastes ef_search budget on inactive/duplicate rows.
        Index(
            "ix_jobs_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=text("is_active AND canonical_id IS NULL AND embedding IS NOT NULL"),
        ),
        Index(
            "ix_jobs_queued",
            "queued_at",
            postgresql_where=text("scrape_status = 'queued'"),
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
    # FAANG+ / Quant / Others, computed at ingest (scraping/categorize.py).
    category: Optional[str] = Field(default=None, max_length=16, index=True)
    # Visa sponsorship analysis ("sponsorship_available", "citizenship", "no_sponsorship"),
    # computed at ingest (scraping/sponsorship.py). Persisting this allows feed queries
    # to filter via B-tree index and defer the heavy description column.
    sponsorship_status: Optional[str] = Field(default=None, max_length=32, index=True)
    sponsorship_label: Optional[str] = Field(default=None, max_length=32)
    # Registrable domain when the apply link is on the company's own site.
    company_domain: Optional[str] = Field(default=None, max_length=255)
    location: Optional[str] = None
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_currency: Optional[str] = Field(default="USD", max_length=3)
    # "hour" or "year". Internship pay is usually hourly; annualizing $50/hr
    # into "$104,000" would misrepresent it.
    salary_period: Optional[str] = Field(default=None, max_length=8)
    apply_url: str
    description: Optional[str] = Field(default=None, sa_column=Column(Text))
    # Which extraction strategy produced `description` (greenhouse, lever,
    # ashby, workday, smartrecruiters, linkedin, jsonld, readability), so
    # per-source yield can be measured.
    description_source: Optional[str] = Field(default=None, max_length=32)
    skills: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    seniority_level: Optional[str] = None
    employment_type: Optional[str] = None
    is_remote: Optional[bool] = None
    terms: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    embedding: Optional[List[float]] = Field(default=None, sa_column=Column(Vector(768)))
    posted_at: Optional[datetime] = None
    # Last time a crawl saw this posting (refreshed even when nothing changed).
    scraped_at: datetime = Field(default_factory=utc_now)
    # Immutable insertion time. Cross-source linking picks the canonical row
    # by this, not scraped_at, which now moves on every crawl and would make
    # the canonical choice flip-flop.
    first_seen_at: datetime = Field(default_factory=utc_now)
    # When process_raw_jobs_batch claimed the row (raw -> queued). The stuck-
    # job reaper keys on this; it used scraped_at, which requeued any old job
    # within minutes of it being claimed.
    queued_at: Optional[datetime] = None
    enriched_at: Optional[datetime] = None
    # When jd_extractor last ATTEMPTED this posting's description (set whether
    # or not it succeeded). Distinguishes "never attempted" from "attempted
    # and unavailable", and bounds retries of unreachable postings
    # (scraping/db_sync.py JD_RETRY_AFTER). The backfill task targets NULLs.
    description_fetched_at: Optional[datetime] = None
    is_active: bool = Field(default=True)
    scrape_status: str = Field(default="raw")