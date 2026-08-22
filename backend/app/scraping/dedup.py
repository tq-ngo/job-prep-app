import re
import hashlib
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.url_seen import UrlSeen
from app.core.redis import create_worker_redis


class JobDeduplicator:
    """
    Handles URL canonicalization and composite SHA-256 fingerprint generation
    to eliminate duplicate listings across job platforms.

    Also provides 2-layer dedup helpers (Redis + DB) used by the BFS
    news crawler.  The 3-layer job dedup lives in db_sync.py.
    """
    
    # Common tracking parameters used by recruitment platforms
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gh_jid", "trkid", "sc_channel", "rb_clickid", "ref", "source"
    }

    def __init__(self):
        # Lazily initialized — single Redis client reused across calls.
        self._redis = None

    def _get_redis(self):
        """Return the shared Redis client, creating it on first use."""
        if self._redis is None:
            self._redis = create_worker_redis()
        return self._redis

    @classmethod
    def canonicalize_url(cls, url: str) -> str:
        """
        Strips tracking parameters, lowercases hostnames, and normalizes URLs.
        Example:
        'HTTP://Jobs.Amazon.com/pv/123/?utm_source=linkedin&ref=foo'
        -> 'https://jobs.amazon.com/pv/123'
        """
        parsed = urlparse(url.strip())
        
        # Enforce https protocol and lowercase hostname
        scheme = "https"
        netloc = parsed.netloc.lower()
        
        # Strip trailing slashes from path
        path = parsed.path.rstrip("/")
        
        # Filter out tracking query parameters
        query_pairs = parse_qsl(parsed.query)
        filtered_query = [
            (k, v) for k, v in query_pairs 
            if k.lower() not in cls.TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_query)
        
        return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))

    @classmethod
    def normalize_text(cls, text: str) -> str:
        """
        Removes special characters, extra whitespace, and converts to lowercase.
        """
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r'[\W_]+', ' ', text) # Replace non-alphanumeric chars with space
        return re.sub(r'\s+', ' ', text).strip()

    @classmethod
    def generate_fingerprint(cls, company: str, title: str, location: str) -> str:
        """
        Creates a composite SHA-256 fingerprint for deduplicating cross-posted listings.
        Fingerprint = SHA256(norm_company + '|' + norm_title + '|' + norm_location)
        """
        norm_company = cls.normalize_text(company)
        norm_title = cls.normalize_text(title)
        norm_location = cls.normalize_text(location)
        
        raw_composite = f"{norm_company}|{norm_title}|{norm_location}"
        return hashlib.sha256(raw_composite.encode("utf-8")).hexdigest()

    @classmethod
    def url_hash(cls, url: str) -> str:
        """SHA-256 of the canonicalized URL."""
        canonical = cls.canonicalize_url(url)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    # ── BFS crawler dedup helpers ────────────────────────────────────────

    async def is_seen(self, url: str, session: AsyncSession) -> bool:
        """
        2-layer check used by the BFS news crawler:
          Layer 1: Redis Set  (fast, shared across workers)
          Layer 2: PostgreSQL url_seen table  (durable, survives Redis eviction)
        """
        url_sha = self.url_hash(url)
        redis = self._get_redis()

        # Layer 1 — Redis
        if await redis.sismember("url_seen_set", url_sha):
            return True

        # Layer 2 — Postgres
        stmt = select(UrlSeen).where(UrlSeen.url_sha256 == url_sha)
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            # Hydrate Redis so the next check short-circuits
            await redis.sadd("url_seen_set", url_sha)
            return True

        return False

    async def mark_seen(
        self, url: str, session: AsyncSession, source_type: str = "news"
    ) -> None:
        """
        Record a URL as visited in both Redis and PostgreSQL.
        """
        url_sha = self.url_hash(url)
        canonical = self.canonicalize_url(url)
        redis = self._get_redis()

        # Redis
        await redis.sadd("url_seen_set", url_sha)

        # Postgres — idempotent (PK = url_sha256)
        existing = await session.get(UrlSeen, url_sha)
        if not existing:
            record = UrlSeen(
                url_sha256=url_sha,
                canonical_url=canonical,
                source_type=source_type,
            )
            session.add(record)
            await session.flush()


dedup_engine = JobDeduplicator()