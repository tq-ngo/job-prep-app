import asyncio
import re
import random
from typing import List, Dict, Callable, Awaitable
from playwright.async_api import async_playwright

class LinkedInScraper:
    def __init__(self):
        pass

    async def _random_delay(self, min_ms: int = 2000, max_ms: int = 5000):
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

    async def fetch_jobs(
        self, 
        base_search_url: str, 
        li_at_cookie: str,
        max_pages: int = 10,
        progress_callback: Callable[[int, str], Awaitable[None]] = None
    ) -> List[Dict]:
        
        extracted_jobs = []
        
        async with async_playwright() as p:
            # Launch browser ONCE for the entire sequential run
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
            
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080}
            )

            # Block unnecessary resources to speed up rendering
            await context.route("**/*.{png,jpg,jpeg,gif,css,woff2}", lambda route: route.abort())

            if li_at_cookie:
                await context.add_cookies([{
                    "name": "li_at",
                    "value": li_at_cookie,
                    "domain": ".www.linkedin.com",
                    "path": "/"
                }])

            page = await context.new_page()
            
            try:
                for page_num in range(max_pages):
                    # LinkedIn paginates by 25 results per page
                    offset = page_num * 25
                    
                    # Ensure base URL has query params before appending
                    separator = "&" if "?" in base_search_url else "?"
                    paginated_url = f"{base_search_url}{separator}start={offset}"
                    
                    if progress_callback:
                        percent = int((page_num / max_pages) * 100)
                        await progress_callback(percent, f"Scraping page {page_num + 1}/{max_pages}")

                    await page.goto(paginated_url, wait_until="domcontentloaded")
                    
                    # Authwall check
                    if "linkedin.com/checkpoint" in page.url or "linkedin.com/authwall" in page.url:
                        if progress_callback:
                            await progress_callback(100, "Scraping blocked by authwall. Session cookie might be expired.")
                        break

                    await self._random_delay(3000, 6000)

                    # Wait for job list
                    try:
                        await page.wait_for_selector(".job-search-card, .jobs-search-results__list-item", timeout=10000)
                    except Exception:
                        # If timeout occurs, it likely means we've hit the end of the results
                        break

                    job_cards = await page.locator(".job-search-card, .jobs-search-results__list-item, .base-card").all()
                    
                    if not job_cards:
                        break

                    for card in job_cards:
                        try:
                            title_el = card.locator(".base-search-card__title, .job-card-list__title")
                            company_el = card.locator(".base-search-card__subtitle, .job-card-container__company-name")
                            location_el = card.locator(".job-search-card__location, .job-card-container__metadata-item")
                            link_el = card.locator("a.base-card__full-link, a.job-card-list__title, a.job-card-container__link")

                            job_title = await title_el.first.inner_text() if await title_el.count() > 0 else "Unknown"
                            company_name = await company_el.first.inner_text() if await company_el.count() > 0 else "Unknown"
                            location = await location_el.first.inner_text() if await location_el.count() > 0 else ""
                            raw_url = await link_el.first.get_attribute("href") if await link_el.count() > 0 else ""
                            clean_url = raw_url.split("?")[0] if raw_url else ""

                            # Extract Job ID for DB external_id (e.g., from .../view/1234567/)
                            external_id = ""
                            match = re.search(r'view/(\d+)', clean_url)
                            if match:
                                external_id = match.group(1)

                            if clean_url and external_id:
                                extracted_jobs.append({
                                    "external_id": external_id,
                                    "source": "linkedin",
                                    "title": job_title.strip(),
                                    "company": company_name.strip(),
                                    "location": location.strip().split("\n")[0],
                                    "apply_url": clean_url,
                                    "source_url": clean_url
                                })
                                
                        except Exception as e:
                            continue
            
            finally:
                await browser.close()
                
        return extracted_jobs
