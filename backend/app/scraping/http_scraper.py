import asyncio
import random
import logging
from typing import Optional, Dict, Any
from urllib.parse import urlparse, urljoin
from curl_cffi import CurlOpt, requests

from app.core.url_guard import CrawlTarget, UnsafeUrlError, resolve_crawl_target
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
        # it (DNS rebinding). The lookup blocks, so it runs off the loop.
        try:
            target = await asyncio.to_thread(resolve_crawl_target, url)
        except UnsafeUrlError as exc:
            logger.error("Refusing to fetch unsafe URL %s: %s", url, exc)
            return None

        # Each domain consults the breaker once per call, not once per retry:
        # in HALF_OPEN only a single probe is admitted, so a second check
        # from our own retry loop would be refused.
        admitted: set = set()

        async def _admit(domain: str) -> bool:
            if domain in admitted:
                return True
            if not await circuit_breaker.allow_request(domain):
                logger.warning("Circuit breaker OPEN for %s — skipping fetch", domain)
                return False
            admitted.add(domain)
            return True

        # The domain of the last failed attempt; charged to the breaker once
        # when the whole call gives up. Charging every retry let one flaky
        # posting (3 attempts) bring a whole ATS host most of the way to OPEN.
        failed_domain: Optional[str] = None

        for attempt in range(1, max_retries + 1):
            hop: CrawlTarget = target
            domain = urlparse(hop.url).netloc.lower()
            if not await _admit(domain):
                return None

            try:
                redirect_count = 0
                while True:
                    # Without a proxy, connect to the IPs validated above
                    # rather than letting curl resolve the name again. A
                    # proxy resolves names itself, so pinning can't apply.
                    pin = hop.curl_resolve() if not proxies else []
                    response = await asyncio.to_thread(
                        requests.get,
                        hop.url,
                        headers=request_headers,
                        impersonate="chrome120",
                        proxies=proxies,
                        timeout=15,
                        allow_redirects=False,
                        curl_options={CurlOpt.RESOLVE: pin} if pin else None,
                    )

                    # Handle 3xx redirects manually to validate destination against SSRF guard
                    if response.status_code in (301, 302, 303, 307, 308):
                        loc = response.headers.get("location") or response.headers.get("Location")
                        if not loc:
                            # Retrying won't make a Location header appear.
                            logger.error("Redirect without Location from %s", hop.url)
                            return None
                        next_url = urljoin(hop.url, loc)
                        try:
                            hop = await asyncio.to_thread(resolve_crawl_target, next_url)
                        except UnsafeUrlError as ssrf_err:
                            logger.error(
                                "Redirect to unsafe URL blocked (%s -> %s): %s",
                                url, next_url, ssrf_err,
                            )
                            return None

                        redirect_count += 1
                        if redirect_count > max_redirects:
                            logger.warning("Too many redirects (> %d) for %s", max_redirects, url)
                            return None

                        domain = urlparse(hop.url).netloc.lower()
                        if not await _admit(domain):
                            return None
                        continue

                    # Terminal response reached
                    if response.status_code == 200:
                        await circuit_breaker.record_success(domain)
                        return response.text
                    elif response.status_code in (429, 503, 403):
                        failed_domain = domain
                        logger.warning(
                            f"Attempt {attempt}/{max_retries}: Encountered status {response.status_code} for {hop.url}. Backing off."
                        )
                        break
                    else:
                        logger.error(f"Unrecoverable HTTP status {response.status_code} for URL: {hop.url}")
                        return None

            except Exception as exc:
                failed_domain = domain
                logger.error(f"Attempt {attempt}/{max_retries} failed for {hop.url} with error: {exc}")

            # Back off before the NEXT attempt only.
            if attempt < max_retries:
                jitter = random.uniform(0.5, 1.5)
                backoff_delay = (base_backoff * (2 ** (attempt - 1))) + jitter
                await asyncio.sleep(backoff_delay)

        if failed_domain:
            await circuit_breaker.record_failure(failed_domain)
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