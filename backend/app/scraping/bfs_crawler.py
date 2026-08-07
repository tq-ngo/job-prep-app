import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from urllib.parse import urlparse, urljoin
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.scraping.dedup import dedup_engine
from app.scraping.circuit_breaker import circuit_breaker
from app.scraping.http_scraper import http_scraper
from app.models.news import NewsArticle

logger = logging.getLogger(__name__)


@dataclass
class CrawlConfig:
    """Configuration for a single BFS crawl run."""
    seed_url: str
    allowed_host_suffix: str       # Only follow links to this domain
    max_depth: int = 2             # How many hops from seed
    max_pages: int = 30            # Total pages to scrape per run
    max_outbound_links: int = 15   # Max links to extract per page
    max_path_segments: int = 8     # Ignore very deep URLs like /a/b/c/d/e/f/g/h/
    per_url_delay_seconds: float = 0.5  # Polite delay


@dataclass  
class CrawlState:
    """Mutable state of an ongoing crawl."""
    pages_visited: int = 0
    queue: deque = field(default_factory=deque)  # BFS queue: [(url, depth)]
    
    def enqueue(self, url: str, depth: int):
        self.queue.append((url, depth))
    
    def dequeue(self) -> tuple[str, int]:
        return self.queue.popleft()
    
    def has_more(self) -> bool:
        return len(self.queue) > 0


class BFSNewsCrawler:
    """
    Breadth-First Search web crawler for news sites.
    
    Algorithm (same as the Java crawl-news-system):
    1. Start with seed URL at depth 0
    2. Fetch page
    3. Extract all links on the page
    4. Filter links: same domain, not too deep, not already seen
    5. Add filtered links to queue at depth+1
    6. Repeat until queue empty or max_pages reached
    
    BFS vs DFS for crawling:
    - BFS: visits close pages first (important for news — recent = shallow)
    - DFS: dives deep quickly (risky — could get stuck in one section)
    - We use BFS: breadth-first = better coverage of a site's front page + sections
    
    "Spiral" crawl from crawl-news-system: 
    Same as BFS but adds a max_path_segments guard to avoid traps like
    /archive/2009/01/02/story/related/more — we cap at 8 path segments.
    """
    
    def __init__(self, config: CrawlConfig):
        self.config = config
        self.seed_domain = urlparse(config.seed_url).netloc
    
    async def run(self, session: AsyncSession) -> dict:
        """
        Execute the BFS crawl.
        Returns stats: {"visited": 25, "new": 20, "skipped_dedup": 5}
        """
        state = CrawlState()
        state.enqueue(self.config.seed_url, depth=0)
        
        stats = {"visited": 0, "new": 0, "skipped_dedup": 0, "errors": 0}
        
        while state.has_more() and state.pages_visited < self.config.max_pages:
            url, depth = state.dequeue()
            
            if depth > self.config.max_depth:
                continue
            
            # ── Dedup Check ───────────────────────────────────────────────
            if await dedup_engine.is_seen(url, session):
                stats["skipped_dedup"] += 1
                continue
            
            # ── Circuit Breaker ────────────────────────────────────────────
            domain = urlparse(url).netloc
            if not await circuit_breaker.allow_request(domain):
                logger.info(f"Circuit OPEN for {domain} — pausing crawl")
                await asyncio.sleep(5)  # Brief pause before continuing
                continue
            
            # ── Fetch & Parse ──────────────────────────────────────────────
            try:
                response = await http_scraper.fetch(url)
                if response is None:
                    continue
                
                html = response.text
                article = self._parse_article(url, html)
                
                # Save to database
                await self._save_article(article, session)
                await dedup_engine.mark_seen(url, session, source_type="news")
                
                # Extract outbound links for next BFS level
                links = self._extract_links(url, html)
                filtered = self._filter_links(links, depth)
                
                for link in filtered:
                    state.enqueue(link, depth + 1)
                
                state.pages_visited += 1
                stats["visited"] += 1
                stats["new"] += 1
                
                # Polite delay between requests
                await asyncio.sleep(self.config.per_url_delay_seconds)
                
            except Exception as e:
                logger.error(f"Error crawling {url}: {e}")
                stats["errors"] += 1
                continue
        
        logger.info(f"BFS crawl complete: {stats}")
        return stats
    
    def _extract_links(self, base_url: str, html: str) -> list[str]:
        """Extract all href links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        links = []
        
        for tag in soup.find_all("a", href=True):
            href = tag["href"]
            # Convert relative URLs to absolute
            # e.g., "/news/article-1" → "https://techcrunch.com/news/article-1"
            absolute = urljoin(base_url, href)
            links.append(absolute)
        
        return links[:self.config.max_outbound_links]
    
    def _filter_links(self, links: list[str], current_depth: int) -> list[str]:
        """
        Filter links to only follow relevant ones.
        
        Filters:
        1. Must be same domain (no external links)
        2. Must be HTTP/HTTPS
        3. Path segments must not exceed max_path_segments
        4. No query strings (often tracking, not content)
        """
        filtered = []
        for url in links:
            parsed = urlparse(url)
            
            # Must match allowed host
            if not parsed.netloc.endswith(self.config.allowed_host_suffix):
                continue
            
            # Must be http or https
            if parsed.scheme not in ("http", "https"):
                continue
            
            # Path depth guard (anti-trap)
            path_segments = [p for p in parsed.path.split("/") if p]
            if len(path_segments) > self.config.max_path_segments:
                continue
            
            # Skip obvious non-article pages
            if any(skip in parsed.path for skip in ["/tag/", "/author/", "/category/", "/page/"]):
                continue
            
            filtered.append(url)
        
        return filtered
    
    def _parse_article(self, url: str, html: str) -> dict:
        """
        Extract article content from HTML.
        
        For a production system, you'd use:
        - newspaper3k: well-known article extractor
        - readability-lxml: Mozilla's Readability algorithm (same as Firefox reader mode)
        - trafilatura: state-of-the-art boilerplate removal
        
        We use a simple BeautifulSoup approach here for clarity.
        """
        soup = BeautifulSoup(html, "lxml")
        
        # Try common article title selectors
        title = None
        for selector in ["h1.article-title", "h1.entry-title", "h1", "title"]:
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break
        
        # Extract article body text
        # Remove navigation, sidebars, footers
        for tag in soup.find_all(["nav", "footer", "aside", "script", "style"]):
            tag.decompose()
        
        # Try common content selectors
        content = ""
        for selector in ["article", ".article-body", ".entry-content", "main"]:
            tag = soup.select_one(selector)
            if tag:
                content = tag.get_text(separator=" ", strip=True)
                break
        
        return {
            "url": url,
            "title": title,
            "content_raw": content[:50000],  # Cap at 50KB
            "html": html,
            "source_domain": urlparse(url).netloc,
        }
    
    async def _save_article(self, article_data: dict, session: AsyncSession):
        """Save article to PostgreSQL with rich metadata and AI summarization."""
        from app.scraping.news_parser import process_and_save_article
        await process_and_save_article(article_data["url"], article_data.get("html", "") or article_data.get("content_raw", ""), session)