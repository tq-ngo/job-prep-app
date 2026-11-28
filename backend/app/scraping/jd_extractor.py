"""
Full job-description extraction and sanitization.
"""
import asyncio
from contextlib import asynccontextmanager
import json
import logging
import re
import time
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, quote, urlparse

from cachetools import TTLCache
import nh3
from bs4 import BeautifulSoup
from markdownify import markdownify

from app.scraping.http_scraper import http_scraper

logger = logging.getLogger(__name__)

_ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "strong", "b", "em", "i", "u", "s", "code", "pre", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "a", "span", "div",
}

_ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}

MAX_JD_CHARS = 40_000
MIN_JD_CHARS = 200

_SAFE_SLUG_RE = re.compile(r"^[A-Za-z0-9_.-]{1,128}$")
_SAFE_DIGITS_RE = re.compile(r"^\d{1,20}$")
_SAFE_UUID_RE = re.compile(r"^[0-9a-fA-F-]{36}$")


def _host_matches(host: str, suffix: str) -> bool:
    """Dot-boundary domain suffix match so `greenhouse.io.evil.com` never matches."""
    host = (host or "").split(":")[0].lower()
    suffix = suffix.lower()
    return host == suffix or host.endswith("." + suffix)


def sanitize_html_to_markdown(html: str) -> Optional[str]:
    """Sanitize untrusted posting HTML and convert it to Markdown."""
    if not html or not html.strip():
        return None

    cleaned = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )

    md = markdownify(cleaned, heading_style="ATX", bullets="-", strip=["a"])

    md = md.replace("\u00a0", " ").replace("\u200b", "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = "\n".join(line.rstrip() for line in md.splitlines()).strip()

    if len(md) < MIN_JD_CHARS:
        return None
    if len(md) > MAX_JD_CHARS:
        md = md[:MAX_JD_CHARS].rsplit("\n", 1)[0] + "\n\n_[description truncated]_"
    return md


def _first_text(html: str, selectors: Iterable[str]) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            inner = el.decode_contents()
            if inner and inner.strip():
                return inner
    return None


# ── Per-source extractors ───────────────────────────────────────────────────

def _extract_linkedin_id(apply_url: str) -> Optional[str]:
    if not apply_url:
        return None
    m = re.search(r"jobs/view/(?:[^/?#]*-)?(\d{6,15})", apply_url)
    return m.group(1) if m else None


async def _from_linkedin(external_id: str) -> Optional[str]:
    if not _SAFE_DIGITS_RE.match(external_id):
        return None
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{external_id}"
    html = await http_scraper.fetch_page(url)
    if not html:
        return None
    inner = _first_text(
        html,
        (
            ".show-more-less-html__markup",
            ".description__text",
            "section.description",
        ),
    )
    return sanitize_html_to_markdown(inner) if inner else None


def _greenhouse_ids(apply_url: str) -> Optional[Tuple[str, str]]:
    parsed = urlparse(apply_url)
    m = re.search(r"^/([^/]+)/jobs/(\d+)", parsed.path)
    if m and m.group(1) != "embed":
        board, job_id = m.group(1), m.group(2)
        if _SAFE_SLUG_RE.match(board) and _SAFE_DIGITS_RE.match(job_id):
            return board, job_id
    qs = parse_qs(parsed.query)
    if parsed.path.startswith("/embed/") and qs.get("for") and qs.get("token"):
        board, job_id = qs["for"][0], qs["token"][0]
        if _SAFE_SLUG_RE.match(board) and _SAFE_DIGITS_RE.match(job_id):
            return board, job_id
    return None


async def _from_greenhouse(apply_url: str) -> Optional[str]:
    ids = _greenhouse_ids(apply_url)
    if not ids:
        return None
    api = (
        f"https://boards-api.greenhouse.io/v1/boards/"
        f"{quote(ids[0], safe='')}/jobs/{quote(ids[1], safe='')}"
    )
    raw = await http_scraper.fetch_page(api)
    if not raw:
        return None
    try:
        content = json.loads(raw).get("content") or ""
    except json.JSONDecodeError:
        return None
    return sanitize_html_to_markdown(unescape(content))


async def _from_lever(apply_url: str) -> Optional[str]:
    parsed = urlparse(apply_url)
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return None
    org, job_id = segments[0], segments[1]
    if not (_SAFE_SLUG_RE.match(org) and _SAFE_UUID_RE.match(job_id)):
        return None
    api = f"https://api.lever.co/v0/postings/{quote(org, safe='')}/{quote(job_id, safe='')}"
    raw = await http_scraper.fetch_page(api)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    parts = [data.get("description") or ""]
    for section in data.get("lists") or []:
        if not isinstance(section, dict):
            continue
        title = section.get("text") or ""
        content = section.get("content") or ""
        if content:
            parts.append(f"<h3>{title}</h3><ul>{content}</ul>" if title else f"<ul>{content}</ul>")
    parts.append(data.get("additional") or "")
    combined = "\n".join(p for p in parts if p)
    return sanitize_html_to_markdown(combined)


_ashby_boards: TTLCache = TTLCache(maxsize=256, ttl=600)


async def _from_ashby(apply_url: str) -> Optional[str]:
    parsed = urlparse(apply_url)
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return None
    org, job_id = segments[0], segments[1].lower()
    if not (_SAFE_SLUG_RE.match(org) and _SAFE_UUID_RE.match(job_id)):
        return None
    jobs = _ashby_boards.get(org)
    if jobs is None:
        raw = await http_scraper.fetch_page(
            f"https://api.ashbyhq.com/posting-api/job-board/{quote(org, safe='')}",
            headers={"Accept": "application/json"},
        )
        if not raw:
            return None
        try:
            jobs = json.loads(raw).get("jobs") or []
        except json.JSONDecodeError:
            return None
        _ashby_boards[org] = jobs
    for job in jobs:
        if str(job.get("id", "")).lower() == job_id:
            return sanitize_html_to_markdown(job.get("descriptionHtml") or "")
    return None


async def _from_workday(apply_url: str) -> Optional[str]:
    parsed = urlparse(apply_url)
    host_m = re.match(r"^([A-Za-z0-9-]+)\.wd\d+\.myworkdayjobs\.com$", parsed.netloc.lower())
    if not host_m:
        return None
    segments = [seg for seg in parsed.path.split("/") if seg]
    if segments and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", segments[0]):
        segments = segments[1:]
    if len(segments) < 3 or segments[1] != "job":
        return None
    site, rest = segments[0], "/".join(quote(seg, safe="") for seg in segments[2:])
    if not _SAFE_SLUG_RE.match(site):
        return None
    api = f"https://{parsed.netloc}/wday/cxs/{host_m.group(1)}/{quote(site, safe='')}/job/{rest}"
    raw = await http_scraper.fetch_page(api, headers={"Accept": "application/json"})
    if not raw:
        return None
    try:
        info = json.loads(raw).get("jobPostingInfo") or {}
    except json.JSONDecodeError:
        return None
    return sanitize_html_to_markdown(info.get("jobDescription") or "")


async def _from_smartrecruiters(apply_url: str) -> Optional[str]:
    parsed = urlparse(apply_url)
    segments = [s for s in parsed.path.split("/") if s]
    if len(segments) < 2:
        return None
    company = segments[0]
    m_id = re.match(r"^(\d+)", segments[1])
    if not (m_id and _SAFE_SLUG_RE.match(company)):
        return None
    posting_id = m_id.group(1)
    api = (
        f"https://api.smartrecruiters.com/v1/companies/"
        f"{quote(company, safe='')}/postings/{quote(posting_id, safe='')}"
    )
    raw = await http_scraper.fetch_page(api, headers={"Accept": "application/json"})
    if not raw:
        return None
    try:
        sections = (json.loads(raw).get("jobAd") or {}).get("sections") or {}
    except json.JSONDecodeError:
        return None
    parts = []
    for name in ("jobDescription", "qualifications", "additionalInformation", "companyDescription"):
        section = sections.get(name) or {}
        if section.get("text"):
            parts.append(f"<h3>{section.get('title') or ''}</h3>{section['text']}")
    return sanitize_html_to_markdown("\n".join(parts))


async def _from_jsonld(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "lxml")
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            payload = json.loads(tag.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        candidates = payload if isinstance(payload, list) else [payload]
        if isinstance(payload, dict) and "@graph" in payload:
            candidates = payload["@graph"]
        for node in candidates:
            if not isinstance(node, dict):
                continue
            types = node.get("@type") or ""
            types = types if isinstance(types, list) else [types]
            if "JobPosting" in types and node.get("description"):
                md = sanitize_html_to_markdown(unescape(str(node["description"])))
                if md:
                    return md
    return None


_BOILERPLATE_PHRASES = (
    "cookies allow websites",
    "accept all cookies",
    "manage cookie preferences",
    "cookie settings",
    "we use cookies to",
    "this site uses cookies",
    "enable javascript",
    "javascript is required to",
    "you need to enable javascript",
)

_JOB_SIGNAL_WORDS = (
    "responsibilities",
    "qualifications",
    "requirements",
    "intern",
    "internship",
    "experience",
    "engineering",
    "developer",
    "skills",
    "compensation",
    "salary",
)


def _strip_cookie_and_chrome_nodes(html: str) -> str:
    """Remove cookie consent banners and page chrome before Readability runs."""
    soup = BeautifulSoup(html, "lxml")
    for el in soup.find_all(["nav", "header", "footer", "aside", "script", "style", "noscript"]):
        el.decompose()
    for selector in (
        "#onetrust-consent-sdk",
        "#CybotCookiebotDialog",
        "#cookie-banner",
        "[id*='cookie' i]",
        "[class*='cookie-banner' i]",
        "[class*='cookie-consent' i]",
        "[class*='consent-banner' i]",
        "[aria-label*='cookie' i]",
    ):
        for el in soup.select(selector):
            if el.name not in ("html", "body", "main", "article"):
                el.decompose()
    return str(soup)


def _looks_like_boilerplate(md: str) -> bool:
    """Return True when extracted text is cookie/JS interstitial boilerplate, not a JD."""
    lower = md.lower()
    has_boilerplate = any(phrase in lower for phrase in _BOILERPLATE_PHRASES)
    if not has_boilerplate:
        return False
    job_signals = sum(1 for word in _JOB_SIGNAL_WORDS if word in lower)
    return job_signals < 2


async def _from_generic(apply_url: str) -> Tuple[Optional[str], Optional[str]]:
    html = await http_scraper.fetch_page(apply_url)
    if not html:
        return None, None

    via_jsonld = await _from_jsonld(html)
    if via_jsonld:
        return via_jsonld, "jsonld"

    cleaned_html = _strip_cookie_and_chrome_nodes(html)
    try:
        from readability import Document

        summary_html = Document(cleaned_html).summary(html_partial=True)
    except Exception as exc:
        logger.debug("readability failed for %s: %s", apply_url, exc)
        return None, None
    md = sanitize_html_to_markdown(summary_html)
    if not md or _looks_like_boilerplate(md):
        return None, None
    return md, "readability"


# ── Public API ──────────────────────────────────────────────────────────────

_ATS_DISPATCH = (
    ("greenhouse.io", _from_greenhouse),
    ("lever.co", _from_lever),
    ("ashbyhq.com", _from_ashby),
    ("myworkdayjobs.com", _from_workday),
    ("smartrecruiters.com", _from_smartrecruiters),
)


async def fetch_jd_with_source(
    apply_url: str,
    source: str,
    external_id: Optional[str] = None,
) -> Tuple[Optional[str], Optional[str]]:
    """Fetch and sanitize the full job description as Markdown."""
    try:
        if source == "linkedin":
            li_id = external_id or _extract_linkedin_id(apply_url)
            if li_id:
                md = await _from_linkedin(li_id)
                if md:
                    return md, "linkedin"
                return None, None

        if not apply_url:
            return None, None

        host = (urlparse(apply_url).netloc or "").lower()
        for suffix, handler in _ATS_DISPATCH:
            if _host_matches(host, suffix):
                md = await handler(apply_url)
                if md:
                    return md, handler.__name__.removeprefix("_from_")
                break

        return await _from_generic(apply_url)
    except Exception as exc:
        logger.warning("JD extraction failed for %s (%s): %s", apply_url, source, exc)
        return None, None


async def fetch_jd(
    apply_url: str,
    source: str,
    external_id: Optional[str] = None,
) -> Optional[str]:
    md, _ = await fetch_jd_with_source(apply_url, source, external_id)
    return md


class DomainRateLimiter:
    """
    Limits concurrent requests per target host domain and spaces requests politely.

    Must be instantiated per task/event loop (never as a module-level singleton
    shared across Celery's per-task event loops).
    """
    def __init__(
        self,
        default_per_domain_limit: int = 2,
        default_interval: float = 0.25,
        linkedin_interval: float = 0.35,
    ):
        self.default_per_domain_limit = default_per_domain_limit
        self.default_interval = default_interval
        self.linkedin_interval = linkedin_interval
        self._semaphores: Dict[str, asyncio.Semaphore] = {}
        self._domain_locks: Dict[str, asyncio.Lock] = {}
        self._last_request_time: Dict[str, float] = {}
        self._lock = asyncio.Lock()

    def get_domain(self, apply_url: str, source: str) -> str:
        if source == "linkedin":
            return "www.linkedin.com"
        host = (urlparse(apply_url).netloc or "").split(":")[0].lower()
        if _host_matches(host, "greenhouse.io"):
            return "boards-api.greenhouse.io"
        if _host_matches(host, "lever.co"):
            return "api.lever.co"
        if _host_matches(host, "ashbyhq.com"):
            return "api.ashbyhq.com"
        if _host_matches(host, "smartrecruiters.com"):
            return "api.smartrecruiters.com"
        return host or "generic"

    async def acquire(self, domain: str):
        async with self._lock:
            if domain not in self._semaphores:
                self._semaphores[domain] = asyncio.Semaphore(self.default_per_domain_limit)
                self._domain_locks[domain] = asyncio.Lock()
            sem = self._semaphores[domain]
            dlock = self._domain_locks[domain]

        await sem.acquire()
        try:
            is_linkedin_domain = _host_matches(domain, "linkedin.com")
            interval = self.linkedin_interval if is_linkedin_domain else self.default_interval
            async with dlock:
                now = time.monotonic()
                last = self._last_request_time.get(domain, 0.0)
                delay = interval - (now - last)
                if delay > 0:
                    await asyncio.sleep(delay)
                self._last_request_time[domain] = time.monotonic()
        except BaseException:
            sem.release()
            raise

    def release(self, domain: str):
        if domain in self._semaphores:
            self._semaphores[domain].release()

    @asynccontextmanager
    async def slot(self, domain: str):
        await self.acquire(domain)
        try:
            yield
        finally:
            self.release(domain)


async def enrich_with_descriptions(
    records: List[Dict[str, Any]],
    concurrency: int = 16,
    domain_limiter: Optional[DomainRateLimiter] = None,
) -> int:
    """
    Populate `description` on scraped job dicts, in place.
    Creates a fresh task-local DomainRateLimiter when none is supplied so
    asyncio primitives never bind to closed Celery event loops.
    """
    if not records:
        return 0

    limiter = domain_limiter or DomainRateLimiter()
    global_semaphore = asyncio.Semaphore(concurrency)
    filled = 0

    groups: Dict[Tuple[str, str, Optional[str]], List[Dict[str, Any]]] = {}
    for r in records:
        if r.get("description"):
            continue
        apply_url = r.get("apply_url") or ""
        source = str(r.get("source") or "")
        external_id = str(r["external_id"]) if r.get("external_id") else None
        # Preserve external_id for LinkedIn even when apply_url is present so
        # _from_linkedin's guest posting API is used instead of authwalled HTML.
        key = (apply_url, source, external_id if source == "linkedin" else None)
        groups.setdefault(key, []).append(r)

    async def fetch_group(key: Tuple[str, str, Optional[str]], group_records: List[Dict[str, Any]]) -> None:
        nonlocal filled
        apply_url, source, external_id = key
        domain = limiter.get_domain(apply_url, source)

        async with global_semaphore:
            async with limiter.slot(domain):
                md, strategy = await fetch_jd_with_source(
                    apply_url=apply_url,
                    source=source,
                    external_id=external_id,
                )

        if md:
            for rec in group_records:
                rec["description"] = md
                rec["description_source"] = strategy
                filled += 1

    results = await asyncio.gather(
        *(fetch_group(k, v) for k, v in groups.items()), return_exceptions=True
    )
    for res in results:
        if isinstance(res, Exception):
            logger.warning("JD batch fetch worker raised: %s", res)

    logger.info(
        "JD extraction: %d/%d records gained a description across %d distinct targets",
        filled,
        len(records),
        len(groups),
    )
    return filled
