import asyncio
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urljoin
from curl_cffi import requests

from app.core.url_guard import UnsafeUrlError, validate_crawl_url
from app.scraping.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

class TLSImpersonateScraper:
    """
    HTTP Engine using curl_cffi to bypass JA3/JA4 TLS fingerprinting checks.
    Impersonates real Chrome browser handshakes at the C layer.
    """
    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
        # Maintain browser headers consistent with Chrome 120
        self.default_headers = {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"macOS"',
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Upgrade-Insecure-Requests": "1",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }

    async def fetch_page(
        self, 
        url: str, 
        max_retries: int = 3, 
        base_backoff: float = 2.0,
        headers: Optional[Dict[str, str]] = None,
        max_redirects: int = 5,
    ) -> Optional[str]:
        """
        Fetches a target URL with TLS impersonation, automatic retries,
        exponential backoff, and randomized jitter.

        `headers` are merged over the browser defaults (e.g. a JSON Accept
        header for ATS APIs that content-negotiate).
        Redirects are followed manually with SSRF checks on each target.
        """
        request_headers = {**self.default_headers, **(headers or {})}
        proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None

        # Re-validate at FETCH time, not just at request time: DNS can
        # re-resolve between the API accepting a URL and the worker fetching
        # it (DNS rebinding).
        try:
            validate_crawl_url(url)
        except UnsafeUrlError as exc:
            logger.error("Refusing to fetch unsafe URL %s: %s", url, exc)
            return None

        for attempt in range(1, max_retries + 1):
            current_url = url
            domain = urlparse(current_url).netloc.lower()

            if not await circuit_breaker.allow_request(domain):
                logger.warning(f"Circuit breaker OPEN for {domain} — skipping fetch for {current_url}")
                return None

            try:
                redirect_count = 0
                while redirect_count <= max_redirects:
                    response = await asyncio.to_thread(
                        requests.get,
                        current_url,
                        headers=request_headers,
                        impersonate="chrome120",
                        proxies=proxies,
                        timeout=15,
                        allow_redirects=False,
                    )

                    # Handle 3xx redirects manually to validate destination against SSRF guard
                    if response.status_code in (301, 302, 303, 307, 308):
                        loc = response.headers.get("location") or response.headers.get("Location")
                        if not loc:
                            break
                        next_url = urljoin(current_url, loc)
                        try:
                            validate_crawl_url(next_url)
                        except UnsafeUrlError as ssrf_err:
                            logger.error(
                                "Redirect to unsafe URL blocked (%s -> %s): %s",
                                current_url, next_url, ssrf_err,
                            )
                            return None

                        redirect_count += 1
                        if redirect_count > max_redirects:
                            logger.warning("Too many redirects (> %d) for %s", max_redirects, url)
                            return None

                        current_url = next_url
                        domain = urlparse(current_url).netloc.lower()
                        if not await circuit_breaker.allow_request(domain):
                            logger.warning(f"Circuit breaker OPEN for redirected domain {domain}")
                            return None
                        continue

                    # Terminal response reached
                    if response.status_code == 200:
                        await circuit_breaker.record_success(domain)
                        return response.text
                    elif response.status_code in (429, 503, 403):
                        await circuit_breaker.record_failure(domain)
                        logger.warning(
                            f"Attempt {attempt}/{max_retries}: Encountered status {response.status_code} for {current_url}. Backing off."
                        )
                        break
                    else:
                        logger.error(f"Unrecoverable HTTP status {response.status_code} for URL: {current_url}")
                        return None

            except Exception as exc:
                await circuit_breaker.record_failure(domain)
                logger.error(f"Attempt {attempt}/{max_retries} failed for {current_url} with error: {exc}")

            # Back off before the NEXT attempt only.
            if attempt < max_retries:
                jitter = random.uniform(0.5, 1.5)
                backoff_delay = (base_backoff * (2 ** (attempt - 1))) + jitter
                await asyncio.sleep(backoff_delay)

        logger.error(f"Failed to fetch {url} after {max_retries} retries.")
        return None

    async def fetch(self, url: str, max_retries: int = 3) -> Optional[Any]:
        """Alias for fetch_page that returns an object with a text attribute for compatibility."""
        text = await self.fetch_page(url, max_retries=max_retries)
        if text is None:
            return None
        class ResponseWrapper:
            def __init__(self, t):
                self.text = t
        return ResponseWrapper(text)


# Singleton instance shared across crawlers and tasks
http_scraper = TLSImpersonateScraper()