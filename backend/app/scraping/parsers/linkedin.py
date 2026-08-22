import asyncio
import re
import random
import logging
from typing import List, Dict, Callable, Awaitable, Optional
from urllib.parse import urlparse, parse_qs, urlencode
from bs4 import BeautifulSoup
from app.scraping.http_scraper import TLSImpersonateScraper

logger = logging.getLogger(__name__)

class LinkedInScraper:
    def __init__(self):
        self.http_scraper = TLSImpersonateScraper()

    async def _random_delay(self, min_ms: int = 500, max_ms: int = 1500):
        await asyncio.sleep(random.uniform(min_ms, max_ms) / 1000)

    async def fetch_jobs(
        self, 
        base_search_url: str, 
        li_at_cookie: str = "",
        max_pages: int = 10,
        progress_callback: Optional[Callable[[int, str], Awaitable[None]]] = None
    ) -> List[Dict]:
        extracted_jobs = []
        
        # Parse search parameters from base_search_url
        parsed_url = urlparse(base_search_url)
        query_params = parse_qs(parsed_url.query)
        keywords = query_params.get("keywords", ["software engineer"])[0]
        location = query_params.get("location", ["United States"])[0]
        
        logger.info(f"Starting LinkedIn guest API scrape for keywords='{keywords}', location='{location}'")
        
        for page_num in range(max_pages):
            offset = page_num * 25
            
            # Construct public guest API endpoint (returns clean server-rendered HTML cards without authwall)
            params = {
                "keywords": keywords,
                "location": location,
                "start": str(offset)
            }
            guest_api_url = f"https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?{urlencode(params)}"
            
            if progress_callback:
                percent = int((page_num / max_pages) * 100)
                await progress_callback(percent, f"Scraping LinkedIn page {page_num + 1}/{max_pages}")

            html_content = await self.http_scraper.fetch_page(guest_api_url)
            if not html_content or not html_content.strip():
                logger.info(f"No more job results returned at offset {offset}")
                break

            soup = BeautifulSoup(html_content, "lxml")
            
            # Find all job cards or link elements
            job_links = soup.find_all("a", href=re.compile(r"linkedin\.com/jobs/view/|/jobs/view/"))
            if not job_links:
                # Fallback to searching card containers
                job_links = soup.select(".base-card__full-link, .job-card-list__title, .job-card-container__link")
                
            if not job_links:
                logger.info(f"No job links found on page {page_num + 1}")
                break

            seen_ids_on_page = set()
            for link_el in job_links:
                try:
                    raw_url = link_el.get("href", "")
                    clean_url = raw_url.split("?")[0] if raw_url else ""
                    if not clean_url:
                        continue
                        
                    # Extract Job ID (external_id) using robust regex matching digits after slug or view/
                    external_id = ""
                    urn_match = re.search(r'[-/](\d{8,12})(?:\?|/|$)', raw_url)
                    if urn_match:
                        external_id = urn_match.group(1)
                    else:
                        id_match = re.search(r'view/(\d+)', clean_url)
                        if id_match:
                            external_id = id_match.group(1)
                            
                    if not external_id or external_id in seen_ids_on_page:
                        continue
                    seen_ids_on_page.add(external_id)

                    # Find parent card container to extract title, company, location
                    card = link_el.find_parent("li") or link_el.find_parent("div", class_=re.compile(r"card|job|result")) or link_el.parent
                    
                    title_el = card.select_one(".base-search-card__title, .job-card-list__title, h3, .sr-only") if card else None
                    company_el = card.select_one(".base-search-card__subtitle, .job-card-container__company-name, h4, .hidden-nested-link") if card else None
                    location_el = card.select_one(".job-search-card__location, .job-card-container__metadata-item") if card else None

                    job_title = title_el.get_text(strip=True) if title_el else link_el.get_text(strip=True)
                    company_name = company_el.get_text(strip=True) if company_el else "Unknown"
                    location_text = location_el.get_text(strip=True) if location_el else ""
                    
                    # Extract posted date from time element if available
                    date_el = card.select_one("time, .job-search-card__listdate, .job-search-card__listdate--new") if card else None
                    posted_at = None
                    if date_el:
                        # LinkedIn uses a `datetime` attribute on <time> elements
                        dt_attr = date_el.get("datetime")
                        if dt_attr:
                            posted_at = dt_attr  # ISO format string, e.g. "2026-08-15"
                    
                    # Determine remote status from location text
                    location_clean = location_text.split("\n")[0].strip()
                    is_remote = bool(re.search(r'\bremote\b', location_clean, re.IGNORECASE))
                    
                    # Clean up common noise in title/company
                    job_title = re.sub(r'\s+', ' ', job_title).strip()
                    company_name = re.sub(r'\s+', ' ', company_name).strip()

                    if job_title and company_name:
                        extracted_jobs.append({
                            "external_id": external_id,
                            "source": "linkedin",
                            "title": job_title,
                            "company": company_name,
                            "location": location_clean,
                            "apply_url": clean_url,
                            "source_url": clean_url,
                            "posted_at": posted_at,
                            "is_remote": is_remote,
                        })
                except Exception as e:
                    logger.debug(f"Error parsing job card: {e}")
                    continue

            await self._random_delay(300, 800)

        if progress_callback:
            await progress_callback(100, f"Completed LinkedIn scrape: found {len(extracted_jobs)} jobs.")

        logger.info(f"LinkedIn scrape complete. Total jobs extracted: {len(extracted_jobs)}")
        return extracted_jobs

