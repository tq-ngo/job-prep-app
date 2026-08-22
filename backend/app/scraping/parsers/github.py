import logging
import re
import uuid
import hashlib
from typing import AsyncIterator, List, Dict, Any
from datetime import datetime, timedelta
import asyncio

from app.scraping.http_scraper import TLSImpersonateScraper
from app.schemas.job import JobCreate

logger = logging.getLogger(__name__)

def parse_relative_date(date_str: str) -> datetime | None:
    date_str = date_str.lower().strip()
    date_str = re.sub(r'[*_]', '', date_str)
    now = datetime.utcnow()
    
    if "today" in date_str:
        return now
    if "yesterday" in date_str:
        return now - timedelta(days=1)
        
    match = re.search(r'(\d+)\s*(d|day|days|w|week|weeks|m|month|months|h|hr|hrs|hour|hours)\b', date_str)
    if match:
        val = int(match.group(1))
        unit = match.group(2)
        if unit.startswith('d'):
            return now - timedelta(days=val)
        elif unit.startswith('w'):
            return now - timedelta(days=val * 7)
        elif unit.startswith('m'):
            return now - timedelta(days=val * 30)
        elif unit.startswith('h'):
            return now - timedelta(hours=val)
            
    match = re.search(r'([a-z]{3})\s+(\d{1,2})', date_str)
    if match:
        month_str = match.group(1).capitalize()
        day_str = match.group(2)
        try:
            parsed_date = datetime.strptime(f"{month_str} {day_str}", "%b %d")
            posted_date = parsed_date.replace(year=now.year)
            if posted_date > now + timedelta(days=1):
                posted_date = posted_date.replace(year=now.year - 1)
            return posted_date
        except ValueError:
            pass
        
    return None

TARGET_URLS = [
    "https://raw.githubusercontent.com/sndsh404/summer-2027-internships/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/refs/heads/dev/README.md",
    "https://raw.githubusercontent.com/zapplyjobs/Internships-2027/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/refs/heads/main/README.md",
]

scraper = TLSImpersonateScraper()

async def _parse_readme(url: str, include_inactive: bool = False) -> Dict[str, Any]:
    logger.info(f"Fetching README from {url}")
    
    text = await scraper.fetch_page(url)
    
    if text is None:
        logger.warning(f"Failed to fetch {url} (circuit open, rate limited, or error)")
        return {"url": url, "jobs": [], "status": "failed"}
    
    in_table = False
    last_company = "Unknown"
    
    jobs_list = []
    skipped_inactive = 0
    
    for line in text.splitlines():
        line = line.strip()
        
        # Detect the start of the internships table
        if line.startswith("| Company | Role |") or line.startswith("|Company|Role|"):
            in_table = True
            continue
            
        # Skip the table separator line
        if in_table and line.startswith("|") and "---" in line:
            continue
            
        if in_table and line.startswith("|"):
            # Parse row
            # Format: | Company | Role | Location | Application/Link | Date Posted |
            parts = [p.strip() for p in line.split("|")]
            
            # parts has empty strings at 0 and -1 because line starts and ends with |
            if len(parts) >= 6:
                company_raw = parts[1]
                role_raw = parts[2]
                location_raw = parts[3]
                link_raw = parts[4]
                date_posted_raw = parts[5]
                
                # 1. Handle company inheritance (↳)
                if company_raw == "↳" or "↳" in company_raw:
                    company = last_company
                else:
                    # Strip any markdown from company (like **Company**)
                    company = re.sub(r'[*_]', '', company_raw).strip()
                    # Remove HTML links if any inside company name
                    company = re.sub(r'<a.*?>(.*?)</a>', r'\1', company)
                    company = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', company)
                    last_company = company
                
                # 2. Check if active
                active = True
                if "🔒" in link_raw or "closed" in link_raw.lower():
                    active = False
                
                if not include_inactive and not active:
                    skipped_inactive += 1
                    continue
                
                # 3. Extract apply URL
                apply_url = ""
                link_match = re.search(r'href="([^"]+)"', link_raw)
                if link_match:
                    apply_url = link_match.group(1)
                else:
                    # fallback to markdown [Link](url)
                    md_match = re.search(r'\[.*?\]\((.*?)\)', link_raw)
                    if md_match:
                        apply_url = md_match.group(1)
                
                if not apply_url:
                    # If it's active but we couldn't parse the URL, skip it.
                    # If it's inactive, we might not have a URL anyway.
                    if active:
                        continue
                    else:
                        apply_url = f"https://github.com/closed-job/{uuid.uuid4()}"
                
                # 4. Extract Location
                # Remove <details><summary>...</summary>
                loc_clean = re.sub(r'<details>\s*<summary>.*?</summary>', '', location_raw)
                loc_clean = re.sub(r'</details>', '', loc_clean)
                # Replace <br/>, </br>, <br> with ;
                loc_clean = re.sub(r'</?br\s*/?>', '; ', loc_clean, flags=re.IGNORECASE)
                # Strip markdown bold/italics
                loc_clean = re.sub(r'[*_]', '', loc_clean).strip()
                
                is_remote = "remote" in loc_clean.lower()
                
                # Clean role text
                role_clean = re.sub(r'[*_]', '', role_raw).strip()
                
                # 5. Generate stable ID
                id_str = f"{company}-{apply_url}"
                stable_id = str(uuid.UUID(hashlib.md5(id_str.encode()).hexdigest()))
                
                job = JobCreate(
                    external_id=stable_id,
                    source="github",
                    source_url=url,
                    title=role_clean,
                    company=company,
                    location=loc_clean,
                    apply_url=apply_url,
                    is_remote=is_remote,
                    posted_at=parse_relative_date(date_posted_raw),
                    terms=None
                )
                jobs_list.append(job)
                
        elif in_table and not line.startswith("|") and line != "":
            # End of table reached
            in_table = False

    logger.info(f"Finished parsing {url}. Yielded {len(jobs_list)}, skipped inactive {skipped_inactive}")
    return {"url": url, "jobs": jobs_list, "status": "success"}

async def parse_github_jobs(include_inactive: bool = False):
    """
    Fetch and parse internship listings concurrently.
    Returns (list_of_jobs, successful_urls)

    NOTE: Previously returned a lazy generator, but successful_urls was
    populated as a side-effect of iteration — meaning it was always empty
    at return time.  Now eagerly collects so successful_urls is reliable
    for the stale-job deactivation logic in job_tasks.py.
    """
    tasks = [_parse_readme(url, include_inactive) for url in TARGET_URLS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful_urls = []
    all_jobs = []

    for res in results:
        if isinstance(res, Exception):
            logger.error(f"README fetch raised: {res}")
            continue
        if isinstance(res, dict) and res.get("status") == "success":
            successful_urls.append(res["url"])
            all_jobs.extend(res["jobs"])

    return all_jobs, successful_urls