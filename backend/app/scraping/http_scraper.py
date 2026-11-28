import asyncio
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urljoin
from curl_cffi import CurlOpt, requests

from app.core.url_guard import CrawlTarget, UnsafeUrlError, resolve_crawl_target
from app.scraping.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)

# Cap scraped HTTP response bodies at 5 MB to prevent worker OOM / decompression bombs.
MAX_RESPONSE_BYTES = 5 * 1024 * 1024
_SENSITIVE_REDIRECT_HEADERS = {"cookie", "authorization"}
_RETRYABLE_STATUSES = {403, 429, 500, 502, 503, 504}


def _strip_sensitive_headers(headers: Dict[str, str]) -> Dict[str, str]:
    return {
        k: v for k, v in headers.items() if k.lower() not in _SENSITIVE_REDIRECT_HEADERS
    }


class TLSImpersonateScraper:
    """
    HTTP Engine using curl_cffi to bypass JA3/JA4 TLS fingerprinting checks.
    Impersonates real Chrome browser handshakes at the C layer.
    """
    def __init__(self, proxy_url: Optional[str] = None):
        self.proxy_url = proxy_url
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
        exponential backoff, randomized jitter, SSRF DNS pinning, cross-host
        credential stripping, and response-size caps.
        """
        base_headers = {**self.default_headers, **(headers or {})}
        proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None

        try:
            target = await asyncio.to_thread(resolve_crawl_target, url)
        except UnsafeUrlError as exc:
            logger.error("Refusing to fetch unsafe URL %s: %s", url, exc)
            return None

        admitted: set = set()

        async def _admit(domain: str) -> bool:
            if domain in admitted:
                return True
            if not await circuit_breaker.allow_request(domain):
                logger.warning("Circuit breaker OPEN for %s — skipping fetch", domain)
                return False
            admitted.add(domain)
            return True

        failed_domain: Optional[str] = None

        for attempt in range(1, max_retries + 1):
            hop: CrawlTarget = target
            domain = urlparse(hop.url).netloc.lower()
            hop_headers = dict(base_headers)
            if not await _admit(domain):
                return None

            try:
                redirect_count = 0
                while True:
                    pin = hop.curl_resolve() if not proxies else []
                    curl_opts = {CurlOpt.RESOLVE: pin} if pin else None
                    response = await asyncio.to_thread(
                        requests.get,
                        hop.url,
                        headers=hop_headers,
                        impersonate="chrome120",
                        proxies=proxies,
                        timeout=15,
                        allow_redirects=False,
                        curl_options=curl_opts,
                    )

                    # Handle 3xx redirects manually to validate destination against SSRF guard
                    if response.status_code in (301, 302, 303, 307, 308):
                        loc = response.headers.get("location") or response.headers.get("Location")
                        if not loc:
                            logger.error("Redirect without Location from %s", hop.url)
                            return None
                        next_url = urljoin(hop.url, loc)
                        prev_host = hop.host
                        try:
                            hop = await asyncio.to_thread(resolve_crawl_target, next_url)
                        except UnsafeUrlError as ssrf_err:
                            logger.error(
                                "Redirect to unsafe URL blocked (%s -> %s): %s",
                                url, next_url, ssrf_err,
                            )
                            return None

                        # Never leak Cookie or Authorization headers across origins.
                        if hop.host != prev_host:
                            hop_headers = _strip_sensitive_headers(hop_headers)

                        redirect_count += 1
                        if redirect_count > max_redirects:
                            logger.warning("Too many redirects (> %d) for %s", max_redirects, url)
                            return None

                        domain = urlparse(hop.url).netloc.lower()
                        if not await _admit(domain):
                            return None
                        continue

                    if response.status_code == 200:
                        content_len = response.headers.get("content-length") or response.headers.get("Content-Length")
                        if content_len and content_len.isdigit() and int(content_len) > MAX_RESPONSE_BYTES:
                            logger.warning("Refusing oversized response (%s bytes) from %s", content_len, hop.url)
                            return None
                        text = response.text
                        if text and len(text.encode("utf-8", errors="ignore")) > MAX_RESPONSE_BYTES:
                            logger.warning("Response body exceeded %d bytes from %s", MAX_RESPONSE_BYTES, hop.url)
                            return None
                        await circuit_breaker.record_success(domain)
                        return text
                    elif response.status_code in _RETRYABLE_STATUSES:
                        failed_domain = domain
                        logger.warning(
                            "Attempt %d/%d: Encountered status %d for %s. Backing off.",
                            attempt, max_retries, response.status_code, hop.url,
                        )
                        break
                    else:
                        logger.error("Unrecoverable HTTP status %d for URL: %s", response.status_code, hop.url)
                        return None

            except Exception as exc:
                failed_domain = domain
                logger.error("Attempt %d/%d failed for %s with error: %s", attempt, max_retries, hop.url, exc)

            if attempt < max_retries:
                jitter = random.uniform(0.5, 1.5)
                backoff_delay = (base_backoff * (2 ** (attempt - 1))) + jitter
                await asyncio.sleep(backoff_delay)

        if failed_domain:
            await circuit_breaker.record_failure(failed_domain)
        logger.error("Failed to fetch %s after %d retries.", url, max_retries)
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


http_scraper = TLSImpersonateScraper()
