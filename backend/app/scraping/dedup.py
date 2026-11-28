import asyncio
import hashlib
import re
import time
import weakref
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from cachetools import LRUCache
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.redis import create_worker_cache_redis
from app.models.url_seen import UrlSeen


class JobDeduplicator:
    """
    Handles URL canonicalization and composite SHA-256 fingerprint generation
    to eliminate duplicate listings across job platforms, plus 3-layer URL
    dedup (LRU -> Redis -> url_seen) used by the news crawlers.
    """

    TRACKING_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "gh_jid", "trkid", "sc_channel", "rb_clickid", "ref", "source",
        "trk", "trackingid", "refid", "lipi", "midtoken", "midsig", "trkemail",
    }

    URL_SEEN_ZSET = "seen:urls"
    URL_SEEN_TTL_SECONDS = 180 * 24 * 3600

    def __init__(self):
        self._redis_by_loop: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, object]" = (
            weakref.WeakKeyDictionary()
        )
        self._seen_urls: LRUCache = LRUCache(maxsize=10_000)

    def _get_redis(self):
        """Return this event loop's cache Redis client, creating it on first use."""
        loop = asyncio.get_running_loop()
        client = self._redis_by_loop.get(loop)
        if client is None:
            client = create_worker_cache_redis()
            self._redis_by_loop[loop] = client
        return client

    @classmethod
    def canonicalize_url(cls, url: str) -> str:
        """Strip tracking parameters, lowercase hostnames, and normalize URLs."""
        parsed = urlparse(url.strip())
        scheme = "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        query_pairs = parse_qsl(parsed.query)
        filtered_query = [
            (k, v) for k, v in query_pairs
            if k.lower() not in cls.TRACKING_PARAMS
        ]
        new_query = urlencode(filtered_query)
        return urlunparse((scheme, netloc, path, parsed.params, new_query, ""))

    @classmethod
    def normalize_text(cls, text: str) -> str:
        if not text:
            return ""
        text = text.lower()
        text = re.sub(r"[\W_]+", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @classmethod
    def generate_fingerprint(cls, company: str, title: str, location: str) -> str:
        norm_company = cls.normalize_text(company)
        norm_title = cls.normalize_text(title)
        norm_location = cls.normalize_text(location)
        raw_composite = f"{norm_company}|{norm_title}|{norm_location}"
        return hashlib.sha256(raw_composite.encode("utf-8")).hexdigest()

    @classmethod
    def url_hash(cls, url: str) -> str:
        canonical = cls.canonicalize_url(url)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def is_seen(self, url: str, session: AsyncSession) -> bool:
        """Sequential 3-layer check: LRU -> Redis ZSET -> url_seen table."""
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
        Durably commit UrlSeen to PostgreSQL FIRST (idempotently via
        ON CONFLICT DO NOTHING), then update Redis and L1 LRU so a DB failure
        or session exit never loses the durable record.
        """
        url_sha = self.url_hash(url)
        canonical = self.canonicalize_url(url)

        bind = session.get_bind()
        if bind is not None and bind.dialect.name == "postgresql":
            stmt = (
                pg_insert(UrlSeen)
                .values(
                    url_sha256=url_sha,
                    canonical_url=canonical,
                    source_type=source_type,
                )
                .on_conflict_do_nothing(index_elements=["url_sha256"])
            )
            await session.execute(stmt)
            await session.commit()
        else:
            existing = await session.get(UrlSeen, url_sha)
            if not existing:
                session.add(
                    UrlSeen(
                        url_sha256=url_sha,
                        canonical_url=canonical,
                        source_type=source_type,
                    )
                )
                try:
                    await session.commit()
                except IntegrityError:
                    await session.rollback()

        redis = self._get_redis()
        now = time.time()
        pipe = redis.pipeline()
        pipe.zadd(self.URL_SEEN_ZSET, {url_sha: now})
        pipe.zremrangebyscore(self.URL_SEEN_ZSET, "-inf", now - self.URL_SEEN_TTL_SECONDS)
        await pipe.execute()
        self._seen_urls[url_sha] = True


dedup_engine = JobDeduplicator()
