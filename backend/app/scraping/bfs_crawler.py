import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraping.dedup import dedup_engine
from app.scraping.http_scraper import http_scraper

logger = logging.getLogger(__name__)


@dataclass
class CrawlConfig:
    """Configuration for a single BFS crawl run."""
    seed_url: str
    allowed_host_suffix: str
    max_depth: int = 2
    max_pages: int = 30
    max_outbound_links: int = 15
    max_path_segments: int = 8
    per_url_delay_seconds: float = 0.5


@dataclass
class CrawlState:
    """Mutable state of an ongoing crawl."""
    pages_visited: int = 0
    queue: deque = field(default_factory=deque)

    def enqueue(self, url: str, depth: int):
        self.queue.append((url, depth))

    def dequeue(self) -> tuple[str, int]:
        return self.queue.popleft()

    def has_more(self) -> bool:
        return len(self.queue) > 0


class BFSNewsCrawler:
    """Breadth-First Search web crawler for news sites."""

    def __init__(self, config: CrawlConfig):
        self.config = config
        self.seed_domain = urlparse(config.seed_url).netloc

    async def run(self, session: AsyncSession) -> dict:
        """
        Execute the BFS crawl.
        NOTE: Circuit breaker admission is owned exclusively by http_scraper.fetch()
        so HALF_OPEN probe locks are never double-claimed and self-deadlocked.
        """
        state = CrawlState()
        state.enqueue(self.config.seed_url, depth=0)

        stats = {"visited": 0, "new": 0, "skipped_dedup": 0, "errors": 0}

        while state.has_more() and state.pages_visited < self.config.max_pages:
            url, depth = state.dequeue()

            if depth > self.config.max_depth:
                continue

            # Do not mark/skip the depth-0 seed index page via dedup so repeated
            # index crawls can still discover new links posted on the homepage.
            if depth > 0 and await dedup_engine.is_seen(url, session):
                stats["skipped_dedup"] += 1
                continue

            try:
                response = await http_scraper.fetch(url)
                if response is None:
                    continue

                html = response.text

                # Depth-0 seed URLs are index pages (e.g. /news); only persist
                # linked articles (depth > 0) as NewsArticle rows.
                if depth > 0:
                    article = self._parse_article(url, html)
                    await self._save_article(article, session)
                    await dedup_engine.mark_seen(url, session, source_type="news")
                    stats["new"] += 1

                if depth < self.config.max_depth:
                    links = self._extract_links(url, html)
                    filtered = self._filter_links(links, depth)[: self.config.max_outbound_links]
                    for link in filtered:
                        state.enqueue(link, depth + 1)

                state.pages_visited += 1
                stats["visited"] += 1

                await asyncio.sleep(self.config.per_url_delay_seconds)

            except Exception as exc:
                await session.rollback()
                logger.error("Error crawling %s: %s", url, exc)
                stats["errors"] += 1
                continue

        logger.info("BFS crawl complete: %s", stats)
        return stats

    def _extract_links(self, base_url: str, html: str) -> list[str]:
        """Extract all href links from HTML (filtering & capping happen in _filter_links)."""
        soup = BeautifulSoup(html, "lxml")
        links = []
        seen = set()
        for tag in soup.find_all("a", href=True):
            absolute = urljoin(base_url, tag["href"])
            if absolute not in seen:
                seen.add(absolute)
                links.append(absolute)
        return links

    def _filter_links(self, links: list[str], current_depth: int) -> list[str]:
        """
        Filter links to only follow relevant same-domain article URLs.
        """
        filtered = []
        suffix = self.config.allowed_host_suffix.lower()
        for url in links:
            parsed = urlparse(url)

            netloc = parsed.netloc.lower()
            if netloc != suffix and not netloc.endswith("." + suffix):
                continue

            if parsed.scheme not in ("http", "https"):
                continue

            # Drop URLs with query strings (usually tracking/pagination traps).
            if parsed.query:
                continue

            path_segments = [p for p in parsed.path.split("/") if p]
            if not path_segments or len(path_segments) > self.config.max_path_segments:
                continue

            if any(skip in parsed.path for skip in ("/tag/", "/author/", "/category/", "/page/")):
                continue

            filtered.append(url)

        return filtered

    def _parse_article(self, url: str, html: str) -> dict:
        soup = BeautifulSoup(html, "lxml")
        title = None
        for selector in ("h1.article-title", "h1.entry-title", "h1", "title"):
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break

        for tag in soup.find_all(["nav", "footer", "aside", "script", "style"]):
            tag.decompose()

        content = ""
        for selector in ("article", ".article-body", ".entry-content", "main"):
            tag = soup.select_one(selector)
            if tag:
                content = tag.get_text(separator=" ", strip=True)
                break

        return {
            "url": url,
            "title": title,
            "content_raw": content[:50000],
            "html": html,
            "source_domain": urlparse(url).netloc,
        }

    async def _save_article(self, article_data: dict, session: AsyncSession):
        from app.tasks.news_tasks import save_article_and_queue_summary

        await save_article_and_queue_summary(
            article_data["url"],
            article_data.get("html", "") or article_data.get("content_raw", ""),
            session,
        )
