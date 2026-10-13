import logging
import random
import uuid

from app.config import settings
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

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


@celery_app.task(name="app.tasks.news_tasks.crawl_news_site", bind=True)
def crawl_news_site(self, url: str):
    from asgiref.sync import async_to_sync
    return async_to_sync(_crawl_news_site)(self, url)

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


@celery_app.task(name="app.tasks.news_tasks.scrape_linkedin_news", bind=True)
def scrape_linkedin_news(self):
    from asgiref.sync import async_to_sync
    return async_to_sync(_scrape_linkedin_news)(self)

async def _scrape_linkedin_news(self):
    logger.info("Crawling LinkedIn Daily News Rundown")

    from bs4 import BeautifulSoup
    from app.core.database import create_worker_session_ctx
    from app.core.redis import create_worker_redis
    from app.scraping.http_scraper import TLSImpersonateScraper
    from app.scraping.news_parser import article_url_hash, find_article, is_fresh

    redis = create_worker_redis()
    lock_key = "scrape_lock:linkedin_news"
    if not await redis.set(lock_key, "locked", nx=True, ex=NEWS_LOCK_TTL_SECONDS):
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
        await redis.delete(lock_key)
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
    from asgiref.sync import async_to_sync
    return async_to_sync(_summarize_article)(self, article_id)

async def _summarize_article(self, article_id: str):
    from app.ai.gemini_client import GeminiTransientError
    from app.core.database import create_worker_session_ctx
    from app.core.datetime_utils import utc_now
    from app.models.news import NewsArticle
    from app.scraping.news_parser import extractive_summary, summarize_with_ai

    async with create_worker_session_ctx() as session:
        article = await session.get(NewsArticle, uuid.UUID(article_id))
        if article is None or article.enriched_at is not None:
            return "skipped"

        title = article.title or ""
        content = article.content_clean or article.summary or ""
        try:
            summary, categories, tags = await summarize_with_ai(
                title, content, fallback_on_transient=False
            )
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
