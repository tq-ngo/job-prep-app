import asyncio
import re
import hashlib
import time
from urllib.parse import urlparse, urlunparse, parse_qsl, urlencode
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import LRUCache

from app.models.url_seen import UrlSeen
from app.core.redis import create_worker_redis


class JobDeduplicator:
    """
    Handles URL canonicalization and composite SHA-256 fingerprint generation
    to eliminate duplicate listings across job platforms.

    Also provides the 3-layer URL dedup (LRU -> Redis -> url_seen) used by
    the news crawlers. The 3-layer job dedup lives in db_sync.py.
    """
    
    # Common tracking parameters used by recruitment platforms
    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gh_jid", "trkid", "sc_channel", "rb_clickid", "ref", "source",
        # LinkedIn appends these to every link, so the same story arrived
        # under many URLs and was stored once per variant.
        "trk", "trackingid", "refid", "lipi", "midtoken", "midsig", "trkemail",
    }

    # Redis ZSET of url sha256 -> epoch seconds. Was a plain SET with no TTL
    # at all, so it grew without bound.
    URL_SEEN_ZSET = "seen:urls"
    URL_SEEN_TTL_SECONDS = 180 * 24 * 3600

    def __init__(self):
        # One Redis client per event loop. Celery runs each task through
        # async_to_sync on a FRESH loop; a single cached client stayed bound
        # to the first task's (closed) loop and failed in every later task.
        self._redis_by_loop: dict = {}
        # Layer 1: per-process LRU of URL hashes confirmed seen.
        self._seen_urls: LRUCache = LRUCache(maxsize=10_000)

    def _get_redis(self):
        """Return this event loop's Redis client, creating it on first use."""
        loop_id = id(asyncio.get_running_loop())
        client = self._redis_by_loop.get(loop_id)
        if client is None:
            if len(self._redis_by_loop) > 8:
                # Bounded like gemini_client: old loops are already closed,
                # so their clients are only dropped, not awaited.
                self._redis_by_loop.clear()
            client = self._redis_by_loop[loop_id] = create_worker_redis()
        return client

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
        Sequential 3-layer check used by the news crawlers:
          Layer 1: in-process LRU     (no network)
          Layer 2: Redis ZSET         (shared across workers, per-entry TTL)
          Layer 3: url_seen table     (durable, survives Redis eviction)
        A lower-layer hit hydrates the layers above it.
        """
        url_sha = self.url_hash(url)
        if url_sha in self._seen_urls:
            return True

        redis = self._get_redis()
        score = await redis.zscore(self.URL_SEEN_ZSET, url_sha)
        if score is not None and float(score) >= time.time() - self.URL_SEEN_TTL_SECONDS:
            self._seen_urls[url_sha] = True
            return True

        stmt = select(UrlSeen).where(UrlSeen.url_sha256 == url_sha)
        result = await session.execute(stmt)
        if result.scalar_one_or_none() is not None:
            await redis.zadd(self.URL_SEEN_ZSET, {url_sha: time.time()})
            self._seen_urls[url_sha] = True
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

        now = time.time()
        pipe = redis.pipeline()
        pipe.zadd(self.URL_SEEN_ZSET, {url_sha: now})
        pipe.zremrangebyscore(self.URL_SEEN_ZSET, "-inf", now - self.URL_SEEN_TTL_SECONDS)
        await pipe.execute()
        self._seen_urls[url_sha] = True

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