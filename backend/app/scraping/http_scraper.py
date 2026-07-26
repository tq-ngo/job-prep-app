import asyncio
import random
import logging
from typing import Optional, Dict, Any
from curl_cffi import requests

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
        base_backoff: float = 2.0
    ) -> Optional[str]:
        """
        Fetches a target URL with TLS impersonation, automatic retries,
        exponential backoff, and randomized jitter.
        """
        proxies = {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None

        for attempt in range(1, max_retries + 1):
            try:
                # Execute blocking curl_cffi call in threadpool to keep asyncio loop unblocked
                response = await asyncio.to_thread(
                    requests.get,
                    url,
                    headers=self.default_headers,
                    impersonate="chrome120", # Exact TLS Cipher Suite & HTTP/2 frame spoofing
                    proxies=proxies,
                    timeout=15,
                    allow_redirects=True
                )

                if response.status_code == 200:
                    return response.text
                elif response.status_code in (429, 503, 403):
                    logger.warning(
                        f"Attempt {attempt}/{max_retries}: Encountered status {response.status_code} for {url}. Backing off."
                    )
                else:
                    logger.error(f"Unrecoverable HTTP status {response.status_code} for URL: {url}")
                    return None

            except Exception as exc:
                logger.error(f"Attempt {attempt}/{max_retries} failed for {url} with error: {exc}")

            # Calculate Exponential Backoff with Jitter: (Base * 2^attempt) + Random(0, 1)
            jitter = random.uniform(0.5, 1.5)
            backoff_delay = (base_backoff * (2 ** (attempt - 1))) + jitter
            await asyncio.sleep(backoff_delay)

        logger.error(f"Failed to fetch {url} after {max_retries} retries.")
        return None