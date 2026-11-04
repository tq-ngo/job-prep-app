import logging
import random
import uuid

from app.config import settings
from app.tasks.celery_app import celery_app
from app.tasks.runtime import HARD_LIMIT_GRACE, run_async

logger = logging.getLogger(__name__)

# A BFS crawl fetches up to 6 pages; LinkedIn News up to 16 (overview plus
# stories), each with retries and backoff.
NEWS_CRAWL_TIMEOUT = 600
LINKEDIN_NEWS_TIMEOUT = 900
# Outlives the hard limit, so a killed run's lock can't expire mid-run.
NEWS_LOCK_TTL_SECONDS = 1800
MAX_LINKEDIN_STORIES = 15


async def save_article_and_queue_summary(url: str, html: str, session):
    """
    Persist an article, then hand summarization to the rate-limited task.

    Summarizing inline used to spend Gemini quota outside the shared rate
    limit (starving job enrichment into 429s) and made one Gemini failure
    abort the whole crawl.
    """
    from app.scraping.news_parser import process_and_save_article

    article = await process_and_save_article(url, html, session)
    if article is not None and article.enriched_at is None:
        summarize_article.delay(str(article.id))
    return article


@celery_app.task(
    name="app.tasks.news_tasks.crawl_news_site",
    bind=True,
    time_limit=NEWS_CRAWL_TIMEOUT + HARD_LIMIT_GRACE,
)
def crawl_news_site(self, url: str):
    return run_async(_crawl_news_site, self, url, timeout=NEWS_CRAWL_TIMEOUT)

async def _crawl_news_site(self, url: str):
    logger.info(f"Crawling news site: {url}")

    from app.core.database import create_worker_session_ctx
    from app.scraping.http_scraper import http_scraper
    from urllib.parse import urlparse

    async with create_worker_session_ctx() as session:
        # Check if URL is a root/index domain or a specific article page
        parsed = urlparse(url)
        is_index_page = parsed.path in ("", "/", "/news", "/latest", "/index.html")

        if is_index_page:
            from app.scraping.bfs_crawler import BFSNewsCrawler, CrawlConfig
            config = CrawlConfig(seed_url=url, allowed_host_suffix=parsed.netloc, max_pages=6, max_depth=1)
            crawler = BFSNewsCrawler(config)
            stats = await crawler.run(session)
            logger.info(f"BFS crawl completed for {url}: {stats}")
            return stats

        # Single article URL scrape
        res = await http_scraper.fetch(url)
        if not res or not res.text:
            logger.error(f"Failed to fetch content from {url}")
            return {"status": "failed", "url": url}

        article = await save_article_and_queue_summary(url, res.text, session)
        if article:
            return {"status": "success", "article_id": str(article.id), "title": article.title}
        return {"status": "failed", "message": "Could not parse or save article"}


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
        await redis.aclose()
        return {"status": "skipped", "reason": "lock_held"}

    try:
        scraper = TLSImpersonateScraper()
        html = await scraper.fetch_page("https://www.linkedin.com/news/")
        if not html:
            return {"status": "failed", "message": "Could not fetch LinkedIn News overview"}

        # The same story is linked from several anchors (headline, image,
        # "see more"), each with different tracking params: collapse them.
        soup = BeautifulSoup(html, "lxml")
        story_urls: list[str] = []
        seen: set[str] = set()
        for link in soup.find_all("a", href=lambda h: h and "/news/story/" in h):
            href = link["href"]
            if href.startswith("/"):
                href = "https://www.linkedin.com" + href
            canonical, _ = article_url_hash(href)
            if canonical not in seen:
                seen.add(canonical)
                story_urls.append(canonical)

        stats = {"scraped": 0, "fresh": 0, "failed": 0, "found": len(story_urls)}
        async with create_worker_session_ctx() as session:
            for story_url in story_urls[:MAX_LINKEDIN_STORIES]:
                # One bad story must not abort the run, as an unguarded
                # exception in the old loop did.
                try:
                    if is_fresh(await find_article(story_url, session)):
                        stats["fresh"] += 1
                        continue
                    story_html = await scraper.fetch_page(story_url)
                    if story_html and await save_article_and_queue_summary(story_url, story_html, session):
                        stats["scraped"] += 1
                    else:
                        stats["failed"] += 1
                except Exception as exc:
                    await session.rollback()
                    stats["failed"] += 1
                    logger.warning("LinkedIn News story failed (%s): %s", story_url, exc)

        logger.info(f"LinkedIn News crawl complete: {stats}")
        return stats
    finally:
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose()


@celery_app.task(
    name="app.tasks.news_tasks.summarize_article",
    bind=True,
    max_retries=3,
    queue="ai",
    # Same quota as job enrichment: summaries used to bypass it entirely.
    rate_limit=settings.GEMINI_RATE_LIMIT,
)
def summarize_article(self, article_id: str):
    return run_async(_summarize_article, self, article_id)

async def _summarize_article(self, article_id: str):
    from app.ai.gemini_client import GeminiThrottled, GeminiTransientError, acquire_gemini_slots
    from app.core.database import create_worker_session_ctx
    from app.core.datetime_utils import utc_now
    from app.core.redis import worker_redis_ctx
    from app.models.news import NewsArticle
    from app.scraping.news_parser import extractive_summary, summarize_with_ai

    async with create_worker_session_ctx() as session:
        article = await session.get(NewsArticle, uuid.UUID(article_id))
        if article is None or article.enriched_at is not None:
            return "skipped"

        title = article.title or ""
        content = article.content_clean or article.summary or ""
        try:
            # Same project-wide budget as job enrichment; summaries used to
            # draw on a separate per-task Celery limit and together they
            # exceeded the quota.
            async with worker_redis_ctx() as redis:
                await acquire_gemini_slots(redis)
            summary, categories, tags = await summarize_with_ai(
                title, content, fallback_on_transient=False
            )
        except GeminiThrottled as exc:
            # No call was made. Re-enqueue a fresh task for when the window
            # resets, instead of spending a retry and eventually degrading to
            # the extractive fallback just because the queue was busy. Safe
            # to repeat: a summarized article is skipped above.
            summarize_article.apply_async((article_id,), countdown=exc.retry_after or 60)
            return "throttled"
        except GeminiTransientError as exc:
            if self.request.retries < self.max_retries:
                countdown = (exc.retry_after or 30) + random.randint(2, 10)
                raise self.retry(exc=exc, countdown=countdown)
            logger.warning("Summary for %s fell back to extractive after retries", article_id)
            summary, categories, tags = extractive_summary(title, content)
        # GeminiConfigError / GeminiTruncatedError propagate: deployment
        # faults must fail loudly, not degrade to extractive output.

        article.summary = summary
        article.categories = categories
        article.tags = tags
        article.enriched_at = utc_now()
        session.add(article)
        await session.commit()
        return "summarized"
