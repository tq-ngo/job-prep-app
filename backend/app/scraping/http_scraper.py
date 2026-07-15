import asyncio
import logging
from urllib.parse import urlparse
from typing import Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.scraping.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

# Realistic browser headers — some sites block requests without these
DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}


class HttpScraper:
    """
    Static page scraper using httpx (async HTTP client).
    
    Use this for:
    - Sites that return full HTML on first load (no JS needed)
    - JSON APIs (RemoteOK, GitHub Simplify)
    - RSS feeds
    
    Features:
    - Connection pooling (one client shared across requests)
    - Automatic retry with exponential backoff
    - Circuit breaker integration
    - Per-domain rate limiting (polite delay between requests)
    - Gzip decompression
    """
    
    # Minimum seconds between requests to the same domain
    # This is "being a good citizen" — don't hammer servers
    MIN_DELAY_PER_DOMAIN = 1.0
    
    def __init__(self):
        # httpx.AsyncClient is like requests.Session but async
        # Limits control the connection pool size
        self._client = httpx.AsyncClient(
            headers=DEFAULT_HEADERS,
            follow_redirects=True,         # Follow 301/302 redirects
            timeout=httpx.Timeout(30.0),   # 30 second total timeout
            limits=httpx.Limits(
                max_connections=20,             # Max simultaneous connections
                max_keepalive_connections=10,   # Keep 10 connections alive
            ),
        )
        # Track last request time per domain for rate limiting
        self._last_request_time: dict[str, float] = {}
    
    @retry(
        # Retry up to 3 times
        stop=stop_after_attempt(3),
        # Wait 1s, then 2s, then 4s between retries (exponential backoff)
        wait=wait_exponential(multiplier=1, min=1, max=8),
        # Only retry on network errors and 5xx responses (not 4xx)
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    )
    async def fetch(self, url: str) -> Optional[httpx.Response]:
        """
        Fetch a URL with circuit breaker, rate limiting, and retries.
        
        Returns the Response object or None if circuit is open.
        Raises httpx exceptions on persistent failures.
        """
        domain = urlparse(url).netloc
        
        # Circuit Breaker Check
        if not await circuit_breaker.allow_request(domain):
            logger.info(f"Skipping {url[:60]} — circuit OPEN for {domain}")
            return None
        
        # Rate Limiting (polite delay)
        await self._polite_delay(domain)
        
        # Actual HTTP Request
        try:
            logger.debug(f"GET {url[:100]}")
            import os
            headers = {}
            gh_token = os.getenv("GITHUB_TOKEN")
            if gh_token and ("githubusercontent.com" in domain or "api.github.com" in domain):
                headers["Authorization"] = f"Bearer {gh_token}"
                
            response = await self._client.get(url, headers=headers)
            
            # Record success even for 4xx (domain is responding)
            # But raise for actual errors so retry logic kicks in
            response.raise_for_status()
            
            await circuit_breaker.record_success(domain)
            return response
            
        except httpx.HTTPStatusError as e:
            # 4xx: client error (bad URL, auth required) — don't retry
            if 400 <= e.response.status_code < 500:
                logger.warning(f"4xx for {url}: {e.response.status_code}")
                if e.response.status_code == 429:
                    logger.warning("Rate limited (429). Returning None to gracefully skip.")
                    await circuit_breaker.record_failure(domain)
                    return None
                await circuit_breaker.record_success(domain)  # Domain is up
                raise
            # 5xx: server error — record failure and retry
            logger.warning(f"5xx for {url}: {e.response.status_code}")
            await circuit_breaker.record_failure(domain)
            raise
            
        except (httpx.TimeoutException, httpx.ConnectError) as e:
            logger.warning(f"Network error for {url}: {e}")
            await circuit_breaker.record_failure(domain)
            raise
    
    async def fetch_json(self, url: str) -> Optional[dict | list]:
        """Fetch a URL and parse the response as JSON."""
        response = await self.fetch(url)
        if response is None:
            return None
        return response.json()
    
    async def _polite_delay(self, domain: str):
        """
        Enforce minimum time between requests to the same domain.
        This prevents overwhelming servers and reduces ban risk.
        """
        import time
        last = self._last_request_time.get(domain, 0)
        elapsed = time.time() - last
        if elapsed < self.MIN_DELAY_PER_DOMAIN:
            await asyncio.sleep(self.MIN_DELAY_PER_DOMAIN - elapsed)
        self._last_request_time[domain] = time.time()
    
    async def close(self):
        await self._client.aclose()


# Singleton — shared across all scraper calls in this process
http_scraper = HttpScraper()