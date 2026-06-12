import asyncio
import os
import random
from typing import List, Dict
from playwright.async_api import async_playwright

class LinkedInScraper:
    def __init__(self):
        # Look for a session cookie injected via env var
        self.li_at_cookie = os.getenv("LINKEDIN_LI_AT", "")

    async def _random_delay(self, min_ms: int = 1000, max_ms: int = 3000):
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

    async def fetch_and_parse(self, search_url: str) -> List[Dict[str, str]]:
        extracted_jobs = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            # Inject the session cookie to bypass login if available
            if self.li_at_cookie:
                await context.add_cookies([{
                    "name": "li_at",
                    "value": self.li_at_cookie,
                    "domain": ".www.linkedin.com",
                    "path": "/"
                }])

            page = await context.new_page()
            
            try:
                await page.goto(search_url, wait_until="domcontentloaded")
                
                # Check if we were redirected to a login page
                current_url = page.url
                if "linkedin.com/checkpoint/lg/login" in current_url or "linkedin.com/authwall" in current_url:
                    print(f"Scraping blocked by authwall. Current URL: {current_url}")
                    return []

                await self._random_delay(2000, 4000)

                # Wait for the job list to render
                try:
                    await page.wait_for_selector(".job-search-card, .jobs-search-results__list-item, .base-card, .base-search-card, .jobs-search-results-list__item, .jobs-search-results-list", timeout=15000)
                except Exception:
                    print(f"Timeout waiting for job cards on {search_url}. Possibly no jobs found or page structure mismatch.")
                    return []

                # LinkedIn uses different DOM structures for logged-in vs logged-out users.
                # This handles the common job card container.
                job_cards = await page.locator(".job-search-card, .jobs-search-results__list-item, .base-card, .base-search-card, .jobs-search-results-list__item").all()

                for card in job_cards:
                    try:
                        # Extract data depending on DOM variation
                        title_el = card.locator(".base-search-card__title, .job-card-list__title, .base-card__title, .job-card-container__link, .artdeco-entity-lockup__title")
                        company_el = card.locator(".base-search-card__subtitle, .job-card-container__company-name, .base-card__subtitle, .job-card-container__primary-description, .artdeco-entity-lockup__subtitle")
                        location_el = card.locator(".job-search-card__location, .job-card-container__metadata-item, .base-search-card__metadata, .job-card-container__metadata-wrapper")
                        link_el = card.locator("a.base-card__full-link, a.job-card-list__title, a.job-card-container__link, a.base-search-card__title-link, a[href*='/jobs/view/']")

                        # If elements exist, get inner text
                        job_title = await title_el.first.inner_text() if await title_el.count() > 0 else "Unknown Title"
                        company_name = await company_el.first.inner_text() if await company_el.count() > 0 else "Unknown Company"
                        location = await location_el.first.inner_text() if await location_el.count() > 0 else "Remote"
                        
                        raw_url = await link_el.first.get_attribute("href") if await link_el.count() > 0 else ""
                        
                        # Clean URL tracking parameters
                        clean_url = raw_url.split("?")[0] if raw_url else ""

                        if clean_url:
                            extracted_jobs.append({
                                "company_name": company_name.strip(),
                                "job_title": job_title.strip(),
                                "location": location.strip().split("\n")[0], # Handle cases with multiple lines in location
                                "job_url": clean_url,
                                "source": "LinkedIn"
                            })
                        else:
                            print(f"Skipping job card: URL not found for {job_title}")
                            
                    except Exception as e:
                        print(f"Failed to parse a job card: {e}")
                        continue
                        
            except Exception as e:
                print(f"Scraping failed: {e}")
            finally:
                await browser.close()
                
        return extracted_jobs
