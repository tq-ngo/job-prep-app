import asyncio
import hashlib
import logging
import random
import uuid
from urllib.parse import urlparse

from app.config import settings
from app.tasks.celery_app import celery_app
from app.tasks.runtime import HARD_LIMIT_GRACE, run_async

logger = logging.getLogger(__name__)

NEWS_CRAWL_TIMEOUT = 600
LINKEDIN_NEWS_TIMEOUT = 900
NEWS_LOCK_TTL_SECONDS = 1800
MAX_LINKEDIN_STORIES = 15
MAX_SUMMARY_THROTTLE_RETRIES = 5


async def save_article_and_queue_summary(url: str, html: str, session):
    """Persist an article, then hand summarization to the rate-limited task."""
    from app.scraping.news_parser import process_and_save_article

    article = await process_and_save_article(url, html, session)
    if article is not None and article.enriched_at is None:
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
    name="app.tasks.news_tasks.scrape_linkedin_news",
    bind=True,
    time_limit=LINKEDIN_NEWS_TIMEOUT + HARD_LIMIT_GRACE,
)
def scrape_linkedin_news(self):
    return run_async(_scrape_linkedin_news, self, timeout=LINKEDIN_NEWS_TIMEOUT)


async def _scrape_linkedin_news(self):
    logger.info("Crawling LinkedIn Daily News Rundown")

    from bs4 import BeautifulSoup
    from app.core.database import create_worker_session_ctx
    from app.core.locks import acquire_lock, release_lock
    from app.core.redis import create_worker_redis
    from app.scraping.http_scraper import TLSImpersonateScraper
    from app.scraping.news_parser import article_url_hash, find_article, is_fresh

    redis = create_worker_redis()
    lock_key = "scrape_lock:linkedin_news"
    lock_token = await acquire_lock(redis, lock_key, NEWS_LOCK_TTL_SECONDS)
    if not lock_token:
        await redis.aclose(close_connection_pool=True)
        return {"status": "skipped", "reason": "lock_held"}

    try:
        scraper = TLSImpersonateScraper()
        html = await scraper.fetch_page("https://www.linkedin.com/news/")
        if not html:
            return {"status": "failed", "message": "Could not fetch LinkedIn News overview"}

        soup = BeautifulSoup(html, "lxml")
        story_urls: list[str] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=lambda h: h and "/news/story/" in h):
            href = link["href"].strip()
            if href.startswith("/"):
                href = "https://www.linkedin.com" + href
            parsed_href = urlparse(href)
            host = (parsed_href.hostname or "").lower()
            if host != "linkedin.com" and not host.endswith(".linkedin.com"):
                continue
            canonical, _ = article_url_hash(href)
            if canonical not in seen:
                seen.add(canonical)
                story_urls.append(canonical)

        stats = {"scraped": 0, "fresh": 0, "failed": 0, "found": len(story_urls)}
        for story_url in story_urls[:MAX_LINKEDIN_STORIES]:
            try:
                async with create_worker_session_ctx() as session:
                    if is_fresh(await find_article(story_url, session)):
                        stats["fresh"] += 1
                        continue
                story_html = await scraper.fetch_page(story_url)
                if not story_html:
                    stats["failed"] += 1
                    continue
                async with create_worker_session_ctx() as session:
                    if await save_article_and_queue_summary(story_url, story_html, session):
                        stats["scraped"] += 1
                    else:
                        stats["failed"] += 1
            except Exception as exc:
                stats["failed"] += 1
                logger.warning("LinkedIn News story failed (%s): %s", story_url, exc)

        logger.info("LinkedIn News crawl complete: %s", stats)
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
    from app.core.datetime_utils import utc_now
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
    return "summarized"
