import logging
from urllib.parse import urlparse
from typing import Optional
from playwright.async_api import async_playwright, Browser, Page, TimeoutError as PWTimeout

from app.scraping.circuit_breaker import circuit_breaker

logger = logging.getLogger(__name__)


class PlaywrightScraper:
    """
    JavaScript-rendered page scraper using Playwright + Chromium.
    
    Use this for:
    - LinkedIn job listings (React SPA)
    - Greenhouse.io / Lever job boards (dynamically loaded)
    - Any site that shows blank content with httpx
    
    How it works:
    1. Launch a real Chromium browser (headless mode — no visible window)
    2. Navigate to the URL
    3. Wait for the page to fully render (JavaScript executes)
    4. Extract the HTML from the rendered DOM
    5. Close the page
    
    Cost vs httpx:
    - 10-100x slower (browser startup, JS execution)
    - 10x more memory (each browser tab uses ~50MB RAM)
    - Use sparingly — only for truly JS-dependent pages
    """
    
    def __init__(self):
        self._playwright = None
        self._browser: Optional[Browser] = None
    
    async def start(self):
        """Initialize Playwright and launch browser. Call once on startup."""
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,           # No GUI
            args=[
                "--no-sandbox",      # Required in Docker containers
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",   # Prevents crashes in Docker
                "--disable-gpu",     # No GPU in headless mode
            ]
        )
        logger.info("Playwright browser started")
    
    async def stop(self):
        """Cleanup. Call on app shutdown."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
    
    async def fetch(
        self, 
        url: str,
        wait_for: str = "networkidle",  # Wait until no network requests for 500ms
        timeout_ms: int = 30000,
    ) -> Optional[str]:
        """
        Navigate to URL and return the full rendered HTML.
        
        wait_for options:
        - "load": Page load event fired
        - "domcontentloaded": DOM ready, JS may still be running
        - "networkidle": No network requests for 500ms (most complete)
        - CSS selector: Wait until element appears (e.g., ".job-listing")
        
        Returns HTML string or None if circuit is open/error.
        """
        domain = urlparse(url).netloc
        
        if not await circuit_breaker.allow_request(domain):
            logger.info(f"Skipping {url[:60]} — circuit OPEN")
            return None
        
        if not self._browser:
            raise RuntimeError("PlaywrightScraper.start() was not called")
        
        # Create a new browser context (= incognito session)
        # Contexts are isolated: cookies/localStorage don't bleed between scrapes
        context = await self._browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1920, "height": 1080},
            # Block images, fonts, stylesheets — we only need HTML/JS
            # This makes Playwright 2-3x faster
        )
        
        # Block unnecessary resources to speed up scraping
        await context.route(
            "**/*.{png,jpg,jpeg,gif,webp,svg,ico,woff,woff2,ttf,css}",
            lambda route: route.abort()
        )
        
        page: Page = await context.new_page()
        
        try:
            await page.goto(url, wait_until=wait_for, timeout=timeout_ms)
            
            # Extract the fully rendered HTML
            html = await page.content()
            
            await circuit_breaker.record_success(domain)
            return html
            
        except PWTimeout:
            logger.warning(f"Playwright timeout for {url}")
            await circuit_breaker.record_failure(domain)
            return None
            
        except Exception as e:
            logger.error(f"Playwright error for {url}: {e}")
            await circuit_breaker.record_failure(domain)
            return None
            
        finally:
            # Always close page and context to free memory
            await page.close()
            await context.close()


# Singleton — initialized once in the FastAPI lifespan
playwright_scraper = PlaywrightScraper()