import logging
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

@celery_app.task(name="app.tasks.news_tasks.crawl_news_site", bind=True)
def crawl_news_site(self, url: str):
    from asgiref.sync import async_to_sync
    return async_to_sync(_crawl_news_site)(self, url)

async def _crawl_news_site(self, url: str):
    logger.info(f"Crawling news site: {url}")
    
    from app.core.database import create_worker_session
    from app.scraping.http_scraper import http_scraper
    from app.scraping.news_parser import process_and_save_article
    from urllib.parse import urlparse
    
    WorkerSession = create_worker_session()
    async with WorkerSession() as session:
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
        else:
            # Single article URL scrape
            res = await http_scraper.fetch(url)
            if not res or not res.text:
                logger.error(f"Failed to fetch content from {url}")
                return {"status": "failed", "url": url}
                
            article = await process_and_save_article(url, res.text, session)
            if article:
                return {"status": "success", "article_id": str(article.id), "title": article.title}
            return {"status": "failed", "message": "Could not parse or save article"}


@celery_app.task(name="app.tasks.news_tasks.scrape_linkedin_news", bind=True)
def scrape_linkedin_news(self):
    from asgiref.sync import async_to_sync
    return async_to_sync(_scrape_linkedin_news)(self)

async def _scrape_linkedin_news(self):
    logger.info("Crawling LinkedIn Daily News Rundown")
    
    from app.core.database import create_worker_session
    from app.scraping.http_scraper import TLSImpersonateScraper
    from app.scraping.news_parser import process_and_save_article
    from bs4 import BeautifulSoup
    
    url = "https://www.linkedin.com/news/"
    scraper = TLSImpersonateScraper()
    html = await scraper.fetch_page(url)
    
    if not html:
        return {"status": "failed", "message": "Could not fetch LinkedIn News overview"}
        
    soup = BeautifulSoup(html, "lxml")
    story_links = soup.find_all("a", href=lambda h: h and "/news/story/" in h)
    
    stats = {"scraped": 0, "failed": 0}
    WorkerSession = create_worker_session()
    
    async with WorkerSession() as session:
        for link in story_links[:15]:
            story_url = link["href"]
            if story_url.startswith("/"):
                story_url = "https://www.linkedin.com" + story_url
                
            story_html = await scraper.fetch_page(story_url)
            if story_html:
                article = await process_and_save_article(story_url, story_html, session)
                if article:
                    stats["scraped"] += 1
                else:
                    stats["failed"] += 1
                    
    logger.info(f"LinkedIn News crawl complete: {stats}")
    return stats
