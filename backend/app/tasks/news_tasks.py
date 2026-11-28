import asyncio
import hashlib
import html as html_lib
import logging
import random
import re
import uuid
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Dict, List, Optional
from urllib.parse import urlparse

from app.config import settings
from app.core.datetime_utils import as_utc, utc_now, utc_today_start
from app.core.events import (
    NEWS_KIND_CREATED,
    NEWS_KIND_PRUNED,
    NEWS_KIND_SUMMARIZED,
    news_event_payload,
    publish_news_event,
)
from app.tasks.celery_app import celery_app
from app.tasks.runtime import HARD_LIMIT_GRACE, run_async

logger = logging.getLogger(__name__)

NEWS_CRAWL_TIMEOUT = 600
GOOGLE_NEWS_TIMEOUT = 900
NEWS_LOCK_TTL_SECONDS = 1800
MAX_GOOGLE_NEWS_STORIES = 15
MAX_SUMMARY_THROTTLE_RETRIES = 5

GOOGLE_NEWS_FEEDS = (
    "https://news.google.com/rss/search?q=(%22software+engineering%22+OR+%22artificial+intelligence%22+OR+%22cloud+computing%22+OR+cybersecurity+OR+semiconductor+OR+OpenAI+OR+Anthropic+OR+%22tech+startup%22+OR+programming)+when:1d&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/headlines/section/topic/TECHNOLOGY?hl=en-US&gl=US&ceid=US:en",
)

_NON_TECH_NOISE_RE = re.compile(
    r"\b(wordle|connections\s+hints?|strands\s+hints?|mini\s+crossword|black\s+friday\s+deals?|cyber\s+monday\s+deals?)\b",
    re.IGNORECASE,
)


async def _best_effort_publish_news(payload: dict) -> None:
    from app.core.redis import worker_redis_ctx

    try:
        async with worker_redis_ctx() as redis:
            await publish_news_event(redis, payload)
    except Exception as exc:
        logger.warning("Failed to publish news SSE event (%s): %s", payload.get("kind"), exc)


async def purge_old_news(session, today_start: Optional[datetime] = None) -> int:
    """Delete articles scraped prior to the current UTC calendar day."""
    from sqlalchemy import delete
    from app.models.news import NewsArticle

    cutoff = today_start or utc_today_start()
    result = await session.execute(
        delete(NewsArticle).where(NewsArticle.scraped_at < cutoff).returning(NewsArticle.id)
    )
    deleted_ids = result.fetchall()
    await session.commit()
    count = len(deleted_ids)
    if count:
        logger.info("Pruned %d news articles from previous days", count)
        await _best_effort_publish_news({"kind": NEWS_KIND_PRUNED, "count": count})
    return count


def parse_google_news_rss(
    xml_text: str,
    *,
    today_start: Optional[datetime] = None,
    limit: int = MAX_GOOGLE_NEWS_STORIES,
) -> List[Dict[str, Optional[str]]]:
    """Parse Google News RSS items from today (UTC), deduplicating by link."""
    from bs4 import BeautifulSoup

    if not xml_text or not xml_text.strip():
        return []

    cutoff = today_start or utc_today_start()
    soup = BeautifulSoup(xml_text, "xml")
    items: List[Dict[str, Optional[str]]] = []
    seen_links: set[str] = set()

    for item in soup.find_all("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if not title_el or not link_el:
            continue
        title = title_el.get_text(strip=True)
        link = link_el.get_text(strip=True)
        if not title or not link or link in seen_links:
            continue
        if _NON_TECH_NOISE_RE.search(title):
            continue

        pub_str = item.find("pubDate").get_text(strip=True) if item.find("pubDate") else ""
        published_at: Optional[datetime] = None
        if pub_str:
            try:
                published_at = as_utc(parsedate_to_datetime(pub_str))
            except (TypeError, ValueError):
                published_at = None

        # Only keep stories published today (UTC); drop older RSS entries.
        if published_at is not None and published_at < cutoff:
            continue

        source_el = item.find("source")
        source_name = source_el.get_text(strip=True) if source_el else None
        source_url = source_el.get("url") if source_el else None

        desc_raw = item.find("description").get_text() if item.find("description") else ""
        desc_text = ""
        if desc_raw:
            desc_soup = BeautifulSoup(desc_raw, "html.parser")
            desc_text = desc_soup.get_text(" ", strip=True)

        seen_links.add(link)
        items.append(
            {
                "title": title,
                "link": link,
                "published_at": published_at.isoformat() if published_at else None,
                "source_name": source_name,
                "source_url": source_url,
                "snippet": desc_text,
            }
        )
        if len(items) >= limit:
            break

    return items


def _looks_like_google_news_shell(html: str, url: str = "") -> bool:
    """Detect Google News JS redirect / consent shells that lack article content."""
    lower = html.lower()
    host = (urlparse(url).hostname or "").lower()
    if host == "news.google.com" or host.endswith(".news.google.com"):
        if "<article" not in lower or "<title>google news</title>" in lower:
            return True
    if "<title>google news</title>" in lower:
        return True
    if "enable javascript" in lower and "<article" not in lower:
        return True
    return False


def _build_rss_fallback_html(item: Dict[str, Optional[str]]) -> str:
    """Construct clean HTML from RSS metadata when the target site blocks scraping."""
    safe_title = html_lib.escape(item.get("title") or "Technology News")
    safe_source = html_lib.escape(item.get("source_name") or "Google News")
    safe_snippet = html_lib.escape(item.get("snippet") or safe_title)
    pub = html_lib.escape(item.get("published_at") or utc_now().isoformat())
    return (
        "<!doctype html><html><head>"
        f"<meta property='og:title' content='{safe_title}'/>"
        f"<meta property='article:published_time' content='{pub}'/>"
        f"<meta name='author' content='{safe_source}'/>"
        f"<meta name='description' content='{safe_snippet}'/>"
        "</head><body><article>"
        f"<h1>{safe_title}</h1>"
        f"<p>{safe_snippet}</p>"
        f"<p>Reported by {safe_source}.</p>"
        "</article></body></html>"
    )


async def save_article_and_queue_summary(url: str, html: str, session):
    """Persist an article, emit a live SSE creation event, and queue summarization."""
    from app.scraping.news_parser import process_and_save_article

    article = await process_and_save_article(url, html, session)
    if article is not None:
        await _best_effort_publish_news(news_event_payload(article, NEWS_KIND_CREATED))
        if article.enriched_at is None:
            await asyncio.to_thread(summarize_article.delay, str(article.id))
    return article


@celery_app.task(
    name="app.tasks.news_tasks.crawl_news_site",
    bind=True,
    time_limit=NEWS_CRAWL_TIMEOUT + HARD_LIMIT_GRACE,
)
def crawl_news_site(self, url: str):
    return run_async(_crawl_news_site, self, url, timeout=NEWS_CRAWL_TIMEOUT)


async def _crawl_news_site(self, url: str):
    logger.info("Crawling news site: %s", url)

    from app.core.database import create_worker_session_ctx
    from app.core.locks import acquire_lock, release_lock
    from app.core.redis import create_worker_redis
    from app.scraping.http_scraper import http_scraper

    redis = create_worker_redis()
    url_digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
    lock_key = f"scrape_lock:news:{url_digest}"
    lock_token = await acquire_lock(redis, lock_key, NEWS_LOCK_TTL_SECONDS)
    if not lock_token:
        await redis.aclose(close_connection_pool=True)
        return {"status": "skipped", "reason": "lock_held"}

    try:
        async with create_worker_session_ctx() as session:
            parsed = urlparse(url)
            is_index_page = parsed.path in ("", "/", "/news", "/latest", "/index.html")

            if is_index_page:
                from app.scraping.bfs_crawler import BFSNewsCrawler, CrawlConfig

                config = CrawlConfig(
                    seed_url=url,
                    allowed_host_suffix=parsed.netloc,
                    max_pages=6,
                    max_depth=1,
                )
                crawler = BFSNewsCrawler(config)
                stats = await crawler.run(session)
                logger.info("BFS crawl completed for %s: %s", url, stats)
                return stats

            res = await http_scraper.fetch(url)
            if not res or not res.text:
                logger.error("Failed to fetch content from %s", url)
                return {"status": "failed", "url": url}

            article = await save_article_and_queue_summary(url, res.text, session)
            if article:
                return {"status": "success", "article_id": str(article.id), "title": article.title}
            return {"status": "failed", "message": "Could not parse or save article"}
    finally:
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose(close_connection_pool=True)


@celery_app.task(
    name="app.tasks.news_tasks.scrape_google_news",
    bind=True,
    time_limit=GOOGLE_NEWS_TIMEOUT + HARD_LIMIT_GRACE,
)
def scrape_google_news(self):
    return run_async(_scrape_google_news, self, timeout=GOOGLE_NEWS_TIMEOUT)


async def _scrape_google_news(self):
    logger.info("Crawling Google Daily Top News")

    from app.core.database import create_worker_session_ctx
    from app.core.locks import acquire_lock, release_lock
    from app.core.redis import create_worker_redis
    from app.scraping.http_scraper import http_scraper
    from app.scraping.news_parser import find_article

    redis = create_worker_redis()
    lock_key = "scrape_lock:google_news"
    lock_token = await acquire_lock(redis, lock_key, NEWS_LOCK_TTL_SECONDS)
    if not lock_token:
        await redis.aclose(close_connection_pool=True)
        return {"status": "skipped", "reason": "lock_held"}

    try:
        today_start = utc_today_start()
        async with create_worker_session_ctx() as session:
            pruned = await purge_old_news(session, today_start)

        candidates: List[Dict[str, Optional[str]]] = []
        seen_links: set[str] = set()
        for feed_url in GOOGLE_NEWS_FEEDS:
            xml_text = await http_scraper.fetch_page(feed_url)
            if not xml_text:
                continue
            for item in parse_google_news_rss(
                xml_text, today_start=today_start, limit=MAX_GOOGLE_NEWS_STORIES
            ):
                if item["link"] not in seen_links:
                    seen_links.add(item["link"])
                    candidates.append(item)
                if len(candidates) >= MAX_GOOGLE_NEWS_STORIES:
                    break
            if len(candidates) >= MAX_GOOGLE_NEWS_STORIES:
                break

        stats = {"pruned": pruned, "scraped": 0, "fresh": 0, "failed": 0, "found": len(candidates)}
        for item in candidates:
            link = item["link"] or ""
            try:
                async with create_worker_session_ctx() as session:
                    existing = await find_article(link, session)
                    if existing and as_utc(existing.scraped_at) >= today_start and existing.enriched_at:
                        stats["fresh"] += 1
                        continue

                html = await http_scraper.fetch_page(link)
                if not html or _looks_like_google_news_shell(html, link):
                    html = _build_rss_fallback_html(item)

                async with create_worker_session_ctx() as session:
                    if await save_article_and_queue_summary(link, html, session):
                        stats["scraped"] += 1
                    else:
                        stats["failed"] += 1
            except Exception as exc:
                stats["failed"] += 1
                logger.warning("Google News story failed (%s): %s", link, exc)

        logger.info("Google News daily crawl complete: %s", stats)
        return stats
    finally:
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose(close_connection_pool=True)


@celery_app.task(
    name="app.tasks.news_tasks.summarize_article",
    bind=True,
    max_retries=3,
    queue="ai",
    rate_limit=settings.GEMINI_RATE_LIMIT,
)
def summarize_article(self, article_id: str, throttle_attempt: int = 0):
    return run_async(_summarize_article, self, article_id, throttle_attempt)


async def _summarize_article(self, article_id: str, throttle_attempt: int = 0):
    from app.ai.gemini_client import (
        GeminiThrottled,
        GeminiTransientError,
        acquire_gemini_slots,
        set_daily_quota_cooldown,
    )
    from app.core.database import create_worker_session_ctx
    from app.core.redis import worker_redis_ctx
    from app.models.news import NewsArticle
    from app.scraping.news_parser import extractive_summary, summarize_with_ai

    aid = uuid.UUID(article_id)

    # 1. Short read session — close before Gemini network I/O.
    async with create_worker_session_ctx() as session:
        article = await session.get(NewsArticle, aid)
        if article is None or article.enriched_at is not None:
            return "skipped"
        title = article.title or ""
        content = article.content_clean or article.summary or ""

    # 2. Gemini summarization with no open DB transaction.
    try:
        async with worker_redis_ctx() as redis:
            await acquire_gemini_slots(redis)
        summary, categories, tags = await summarize_with_ai(
            title, content, fallback_on_transient=False
        )
    except GeminiThrottled as exc:
        if throttle_attempt < MAX_SUMMARY_THROTTLE_RETRIES:
            await asyncio.to_thread(
                summarize_article.apply_async,
                (article_id, throttle_attempt + 1),
                countdown=exc.retry_after or 60,
            )
            return "throttled"
        logger.warning(
            "Summary for %s exceeded max throttle retries (%d); using extractive fallback",
            article_id,
            MAX_SUMMARY_THROTTLE_RETRIES,
        )
        summary, categories, tags = extractive_summary(title, content)
    except GeminiTransientError as exc:
        if exc.is_daily_quota:
            async with worker_redis_ctx() as redis:
                await set_daily_quota_cooldown(redis, exc.retry_after or 900)
            summary, categories, tags = extractive_summary(title, content)
        elif self.request.retries < self.max_retries:
            countdown = (exc.retry_after or 30) + random.randint(2, 10)
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.warning("Summary for %s fell back to extractive after retries", article_id)
            summary, categories, tags = extractive_summary(title, content)

    # 3. Short write session.
    async with create_worker_session_ctx() as session:
        article = await session.get(NewsArticle, aid)
        if article is None or article.enriched_at is not None:
            return "skipped"
        article.summary = summary
        article.categories = categories
        article.tags = tags
        article.enriched_at = utc_now()
        session.add(article)
        await session.commit()
        await session.refresh(article)

    await _best_effort_publish_news(news_event_payload(article, NEWS_KIND_SUMMARIZED))
    return "summarized"
