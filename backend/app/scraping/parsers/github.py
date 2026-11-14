import logging
import re
import uuid
import hashlib
from typing import AsyncIterator, List, Dict, Any
from datetime import datetime, timedelta, timezone
import asyncio

from urllib.parse import urlparse

from app.scraping.dedup import JobDeduplicator
from app.scraping.http_scraper import TLSImpersonateScraper
from app.schemas.job import JobCreate
from app.core.datetime_utils import utc_now

logger = logging.getLogger(__name__)

def parse_relative_date(date_str: str) -> datetime | None:
    date_str = date_str.lower().strip()
    date_str = re.sub(r'[*_]', '', date_str)
    now = utc_now()
    
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
            # strptime yields a naive datetime; `now` is aware, so attach UTC
            # before any comparison or DB write.
            posted_date = parsed_date.replace(year=now.year, tzinfo=timezone.utc)
            if posted_date > now + timedelta(days=1):
                posted_date = posted_date.replace(year=now.year - 1)
            return posted_date
        except ValueError:
            pass
        
    return None

from html.parser import HTMLParser

TARGET_URLS = [
    "https://raw.githubusercontent.com/SimplifyJobs/Summer2027-Internships/refs/heads/dev/README.md",
    "https://raw.githubusercontent.com/speedyapply/2027-SWE-College-Jobs/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/zshah101/Automated-List-Of-Summer-2027-and-Fall-2026-Tech-Internships/refs/heads/main/README.md",
    "https://raw.githubusercontent.com/vanshb03/Summer2027-Internships/refs/heads/dev/README.md",
]

scraper = TLSImpersonateScraper()


def _clean_company(company_raw: str, last_company: str) -> tuple[str, str]:
    if not company_raw:
        return last_company, last_company
    if "↳" in company_raw:
        return last_company, last_company
    clean = re.sub(r'<a.*?>(.*?)</a>', r'\1', company_raw)
    clean = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean)
    clean = re.sub(r'<.*?>', '', clean)
    clean = re.sub(r'[*_`]', '', clean).strip()
    clean = re.sub(r'^[^\w]+', '', clean).strip()
    if clean:
        return clean, clean
    return last_company, last_company


def _clean_role(role_raw: str) -> str:
    clean = re.sub(r'<.*?>', '', role_raw)
    clean = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', clean)
    clean = re.sub(r'[*_`]', '', clean)
    clean = re.sub(r'[🆕🔥🎓🔒]+', '', clean).strip()
    return re.sub(r'\s+', ' ', clean).strip()


def _clean_location(loc_raw: str) -> tuple[str, bool]:
    clean = re.sub(r'<details>\s*<summary>.*?</summary>', '', loc_raw, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'</details>', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'</?br\s*/?>', '; ', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<.*?>', '', clean)
    clean = re.sub(r'[*_`]', '', clean).strip()
    is_remote = "remote" in clean.lower()
    return clean, is_remote


def _extract_apply_url(link_raw: str) -> str:
    if not link_raw:
        return ""
    m = re.search(r'href=[\"\']([^\"\']+)[\"\']', link_raw, re.IGNORECASE)
    if m:
        url = m.group(1).strip()
    else:
        m2 = re.search(r'\[.*?\]\((https?://[^)]+)\)', link_raw)
        if m2:
            url = m2.group(1).strip()
        else:
            m3 = re.search(r'(https?://[^\s\"\'<>]+)', link_raw)
            url = m3.group(1).strip() if m3 else ""
    if url:
        parsed = urlparse(url)
        if parsed.scheme.lower() in ("http", "https") and parsed.netloc:
            return JobDeduplicator.canonicalize_url(url)
    return ""


def _is_active_role(link_raw: str, role_raw: str = "") -> bool:
    combined = f"{link_raw} {role_raw}".lower()
    if "🔒" in combined or "closed" in combined or "inactive" in combined:
        return False
    return True


class _HTMLTableExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_table = False
        self.in_thead = False
        self.in_tbody = False
        self.in_th = False
        self.in_td = False
        self.current_headers: List[str] = []
        self.current_row: List[str] = []
        self.current_cell: List[str] = []
        self.tables: List[tuple[List[str], List[str]]] = []

    def handle_starttag(self, tag: str, attrs: list):
        attrs_dict = dict(attrs)
        if tag == "table":
            self.in_table = True
            self.current_headers = []
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "th":
            self.in_th = True
            self.current_cell = []
        elif tag == "td":
            self.in_td = True
            self.current_cell = []
        elif tag == "a" and (self.in_td or self.in_th):
            href = attrs_dict.get("href", "")
            self.current_cell.append(f'<a href="{href}">')

    def handle_endtag(self, tag: str):
        if tag == "table":
            self.in_table = False
        elif tag == "thead":
            self.in_thead = False
        elif tag == "tbody":
            self.in_tbody = False
        elif tag == "th":
            self.in_th = False
            self.current_headers.append("".join(self.current_cell).strip())
        elif tag == "td":
            self.in_td = False
            self.current_row.append("".join(self.current_cell).strip())
        elif tag == "a" and (self.in_td or self.in_th):
            self.current_cell.append("</a>")
        elif tag == "tr":
            if self.current_row:
                self.tables.append((list(self.current_headers), list(self.current_row)))
                self.current_row = []

    def handle_data(self, data: str):
        if self.in_th or self.in_td:
            self.current_cell.append(data)


def _parse_html_tables(text: str, source_url: str, include_inactive: bool = False) -> tuple[List[JobCreate], int]:
    extractor = _HTMLTableExtractor()
    extractor.feed(text)
    jobs: List[JobCreate] = []
    skipped_inactive = 0
    last_company = "Unknown"

    for headers, row in extractor.tables:
        if not headers or len(row) < 3:
            continue
        h_lower = [h.lower() for h in headers]
        col_map: Dict[str, int] = {}
        for idx, h in enumerate(h_lower):
            if "company" in h:
                col_map["company"] = idx
            elif "role" in h or "position" in h:
                col_map["role"] = idx
            elif "location" in h:
                col_map["location"] = idx
            elif any(k in h for k in ["application", "apply", "link", "posting"]):
                col_map["link"] = idx
            elif any(k in h for k in ["date", "posted", "age"]):
                col_map["date"] = idx

        if "company" not in col_map or ("role" not in col_map and "position" not in col_map):
            continue

        comp_idx = col_map["company"]
        role_idx = col_map.get("role", 1)
        loc_idx = col_map.get("location", 2)
        link_idx = col_map.get("link", 3)
        date_idx = col_map.get("date", 4)

        comp_raw = row[comp_idx] if comp_idx < len(row) else ""
        role_raw = row[role_idx] if role_idx < len(row) else ""
        loc_raw = row[loc_idx] if loc_idx < len(row) else ""
        link_raw = row[link_idx] if link_idx < len(row) else ""
        date_raw = row[date_idx] if date_idx < len(row) else ""

        active = _is_active_role(link_raw, role_raw)
        if not include_inactive and not active:
            skipped_inactive += 1
            continue

        company, last_company = _clean_company(comp_raw, last_company)
        role = _clean_role(role_raw)
        location, is_remote = _clean_location(loc_raw)
        apply_url = _extract_apply_url(link_raw)

        if not apply_url:
            if active:
                continue
            apply_url = f"https://github.com/closed-job/{uuid.uuid4()}"

        if company and role:
            id_str = f"{company}-{apply_url}"
            stable_id = str(uuid.UUID(hashlib.md5(id_str.encode()).hexdigest()))
            jobs.append(
                JobCreate(
                    external_id=stable_id,
                    source="github",
                    source_url=source_url,
                    title=role,
                    company=company,
                    location=location,
                    apply_url=apply_url,
                    is_remote=is_remote,
                    posted_at=parse_relative_date(date_raw),
                    terms=None,
                )
            )

    return jobs, skipped_inactive


def _parse_markdown_tables(text: str, source_url: str, include_inactive: bool = False) -> tuple[List[JobCreate], int]:
    jobs: List[JobCreate] = []
    skipped_inactive = 0
    lines = text.splitlines()
    in_table = False
    col_map: Dict[str, int] = {}
    last_company = "Unknown"

    for line in lines:
        line = line.strip()
        if not line.startswith("|"):
            if in_table and line != "":
                in_table = False
            continue

        parts = [p.strip() for p in line.split("|")]
        if parts and parts[0] == "":
            parts.pop(0)
        if parts and parts[-1] == "":
            parts.pop()

        p_lower = [p.lower() for p in parts]
        if any("company" in p for p in p_lower) and any(r in p for p in p_lower for r in ["role", "position"]):
            in_table = True
            col_map = {}
            for idx, p in enumerate(p_lower):
                if "company" in p:
                    col_map["company"] = idx
                elif "role" in p or "position" in p:
                    col_map["role"] = idx
                elif "location" in p:
                    col_map["location"] = idx
                elif any(k in p for k in ["application", "apply", "link", "posting"]):
                    col_map["link"] = idx
                elif any(k in p for k in ["date", "posted", "age"]):
                    col_map["date"] = idx
            continue

        if in_table and any("---" in p for p in parts):
            continue

        if in_table and "company" in col_map and ("role" in col_map or "position" in col_map):
            comp_idx = col_map["company"]
            role_idx = col_map.get("role", 1)
            loc_idx = col_map.get("location", 2)
            link_idx = col_map.get("link", 3)
            date_idx = col_map.get("date", 4)

            comp_raw = parts[comp_idx] if comp_idx < len(parts) else ""
            role_raw = parts[role_idx] if role_idx < len(parts) else ""
            loc_raw = parts[loc_idx] if loc_idx < len(parts) else ""
            link_raw = parts[link_idx] if link_idx < len(parts) else ""
            date_raw = parts[date_idx] if date_idx < len(parts) else ""

            active = _is_active_role(link_raw, role_raw)
            if not include_inactive and not active:
                skipped_inactive += 1
                continue

            company, last_company = _clean_company(comp_raw, last_company)
            role = _clean_role(role_raw)
            location, is_remote = _clean_location(loc_raw)
            apply_url = _extract_apply_url(link_raw)

            if not apply_url:
                if active:
                    continue
                apply_url = f"https://github.com/closed-job/{uuid.uuid4()}"

            if company and role:
                id_str = f"{company}-{apply_url}"
                stable_id = str(uuid.UUID(hashlib.md5(id_str.encode()).hexdigest()))
                jobs.append(
                    JobCreate(
                        external_id=stable_id,
                        source="github",
                        source_url=source_url,
                        title=role,
                        company=company,
                        location=location,
                        apply_url=apply_url,
                        is_remote=is_remote,
                        posted_at=parse_relative_date(date_raw),
                        terms=None,
                    )
                )

    return jobs, skipped_inactive


async def _parse_readme(url: str, include_inactive: bool = False) -> Dict[str, Any]:
    logger.info(f"Fetching README from {url}")

    text = await scraper.fetch_page(url)

    if text is None:
        logger.warning(f"Failed to fetch {url} (circuit open, rate limited, or error)")
        return {"url": url, "jobs": [], "status": "failed"}

    if "<table" in text:
        jobs_list, skipped_inactive = _parse_html_tables(text, url, include_inactive)
    else:
        jobs_list, skipped_inactive = _parse_markdown_tables(text, url, include_inactive)

    logger.info(f"Finished parsing {url}. Yielded {len(jobs_list)}, skipped inactive {skipped_inactive}")
    return {"url": url, "jobs": jobs_list, "status": "success"}


async def parse_github_jobs(include_inactive: bool = False):
    """
    Fetch and parse internship listings concurrently.
    Returns (list_of_jobs, successful_urls)

    NOTE: Previously returned a lazy generator, but successful_urls was
    populated as a side-effect of iteration — meaning it was always empty
    at return time. Now eagerly collects so successful_urls is reliable
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