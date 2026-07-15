import hashlib
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode
import logging
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import redis.asyncio as aioredis
from app.core.redis import get_redis_pool

# Parameters that add tracking noise but don't change content
IGNORED_PARAMS = frozenset({
    "utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term",
    "ref", "referrer", "source", "fbclid", "gclid", "mc_eid",
})


def canonicalize_url(url: str) -> str:
    """
    Normalize a URL so that equivalent URLs produce the same string.
    
    Transformations:
    1. Lowercase scheme and host
    2. Remove default ports (http:80, https:443)
    3. Remove tracking query parameters
    4. Sort remaining query parameters (a=1&b=2 == b=2&a=1)
    5. Remove trailing slash from path
    6. Remove URL fragment (#section — server never sees this)
    
    Examples:
        https://Example.com/Jobs/?ref=twitter&page=1
        → https://example.com/Jobs?page=1
        
        HTTP://REMOTEOK.COM/remote-python-jobs
        → http://remoteok.com/remote-python-jobs
    """
    parsed = urlparse(url.strip())
    
    # 1. Lowercase scheme and netloc (host)
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    
    # 2. Remove default ports
    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    elif netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]
    
    # 3 & 4. Filter and sort query params
    query_params = parse_qs(parsed.query, keep_blank_values=False)
    filtered_params = {
        k: v for k, v in query_params.items()
        if k not in IGNORED_PARAMS
    }
    sorted_query = urlencode(sorted(filtered_params.items()), doseq=True)
    
    # 5. Remove trailing slash, but keep root path
    path = parsed.path.rstrip("/") or "/"
    
    # 6. Reconstruct without fragment
    canonical = urlunparse((scheme, netloc, path, "", sorted_query, ""))
    return canonical


def url_to_sha256(url: str) -> str:
    """
    Convert a canonical URL to its SHA-256 hex digest.
    
    SHA-256 produces a fixed 64-character hex string regardless of URL length.
    Using sha256 (not md5) because MD5 has known collision vulnerabilities —
    two different URLs could theoretically produce the same MD5 hash.
    
    Example:
        "https://remoteok.com/jobs/123" 
        → "a3f8c2d1e9b7..." (64 hex chars)
    """
    canonical = canonicalize_url(url)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


logger = logging.getLogger(__name__)

# TTL for Redis dedup keys: 7 days
# After 7 days, a URL can be re-crawled (for job board freshness)
REDIS_DEDUP_TTL_SECONDS = 7 * 24 * 3600

# Redis key prefix for dedup
REDIS_DEDUP_PREFIX = "crawl:v1:url:"


class DeduplicationEngine:
    """
    3-layer URL deduplication engine.
    
    Usage:
        dedup = DeduplicationEngine()
        
        async def scrape(url: str):
            if await dedup.is_seen(url, session):
                return  # Already processed
            # ... do the scraping ...
            await dedup.mark_seen(url, session, source_type="job")
    """
    
    def __init__(self):
        # Layer 1: In-memory set (per worker process lifetime)
        # This is a Python set — lives in RAM, dies with the process
        self._memory_seen: set[str] = set()
    
    async def is_seen(
        self, 
        url: str, 
        session: AsyncSession
    ) -> bool:
        """
        Check all 3 layers. Returns True if URL was already processed.
        Short-circuits as soon as any layer says "seen."
        """
        sha256 = url_to_sha256(url)
        
        # Layer 1: In-memory (fastest)
        if sha256 in self._memory_seen:
            logger.debug(f"Dedup L1 hit: {url[:60]}")
            return True
        
        # Layer 2: Redis
        redis_client = await get_redis_pool()
        redis_key = f"{REDIS_DEDUP_PREFIX}{sha256}"
        
        # EXISTS returns 1 if key exists, 0 if not
        # This is a single round-trip (fast)
        exists = await redis_client.exists(redis_key)
        if exists:
            # Promote to Layer 1 so next check is even faster
            self._memory_seen.add(sha256)
            logger.debug(f"Dedup L2 hit: {url[:60]}")
            return True
        
        # Layer 3: PostgreSQL (durable)
        result = await session.execute(
            text("SELECT 1 FROM url_seen WHERE url_sha256 = :sha256"),
            {"sha256": sha256}
        )
        if result.scalar():
            # Promote to L2 so future workers don't hit the DB
            await redis_client.setex(redis_key, REDIS_DEDUP_TTL_SECONDS, "1")
            # Promote to L1 for this process
            self._memory_seen.add(sha256)
            logger.debug(f"Dedup L3 hit: {url[:60]}")
            return True
        
        return False  # URL is genuinely new
    
    async def mark_seen(
        self,
        url: str,
        session: AsyncSession,
        source_type: str = "job"
    ) -> bool:
        """
        Record a URL as seen in all 3 layers.
        
        The PostgreSQL insert uses ON CONFLICT DO NOTHING:
        If two workers race to process the same URL, only one wins.
        The other silently does nothing — no error, no duplicate.
        
        Returns True if this was a new URL, False if already existed.
        """
        sha256 = url_to_sha256(url)
        canonical = canonicalize_url(url)
        
        # Layer 3: PostgreSQL (do this first — most durable)
        result = await session.execute(
            text("""
                INSERT INTO url_seen (url_sha256, canonical_url, source_type)
                VALUES (:sha256, :url, :source_type)
                ON CONFLICT (url_sha256) DO NOTHING
                RETURNING url_sha256
            """),
            {"sha256": sha256, "url": canonical, "source_type": source_type}
        )
        was_inserted = result.scalar() is not None
        
        if not was_inserted:
            # Another worker won the race — this URL was already inserted
            return False
        
        # Layer 2: Redis
        redis_client = await get_redis_pool()
        redis_key = f"{REDIS_DEDUP_PREFIX}{sha256}"
        await redis_client.setex(redis_key, REDIS_DEDUP_TTL_SECONDS, "1")
        
        # Layer 1: Memory
        self._memory_seen.add(sha256)
        
        logger.info(f"Dedup: marked NEW url {url[:60]}")
        return True


# Module-level singleton — one instance per worker process
# This is intentional: the in-memory set accumulates within a process lifetime
dedup_engine = DeduplicationEngine()