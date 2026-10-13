"""
Full job-description extraction and sanitization.

Neither crawler used to fetch a description: parsers/linkedin.py and
parsers/github.py both emitted metadata only, so `jobs.description` was NULL
for every row. That single gap made Gemini skill extraction, pgvector
embeddings, /search/semantic and the UI's job-detail drawer all inert.

This module adds the missing stage. Given a job record it fetches the real
posting body, sanitizes it, and converts it to Markdown for storage:

    LinkedIn  -> /jobs-guest/jobs/api/jobPosting/{id}   (server-rendered)
    Greenhouse     -> boards-api.greenhouse.io/v1/boards/...      (JSON)
    Lever          -> api.lever.co/v0/postings/...                (JSON)
    Ashby          -> api.ashbyhq.com/posting-api/job-board/...   (JSON)
    Workday        -> {tenant}.wdN.myworkdayjobs.com/wday/cxs/... (JSON)
    SmartRecruiters-> api.smartrecruiters.com/v1/companies/...    (JSON)
    other          -> JSON-LD, else readability-lxml main content

Ashby, Workday and SmartRecruiters render client-side, so the generic path
usually got a JS shell for them; their public JSON APIs are the reliable
source.

Storage format is Markdown, not raw HTML: sanitizing once at write time means
the frontend never needs dangerouslySetInnerHTML, so a malicious posting can't
become stored XSS on every render.
"""
import asyncio
import json
import logging
import random
import re
from html import unescape
from typing import Any, Dict, Iterable, List, Optional, Tuple
from urllib.parse import parse_qs, urlparse

from cachetools import TTLCache

import nh3
from bs4 import BeautifulSoup
from markdownify import markdownify

from app.scraping.http_scraper import http_scraper

logger = logging.getLogger(__name__)

# Tags worth keeping in a job description. Deliberately EXCLUDES:
#   img / picture / source  -> 1x1 tracking pixels. nh3's default allowlist
#                              keeps <img>, which would preserve exactly the
#                              beacons the requirement says to strip.
#   iframe / object / embed -> third-party frames
#   script / style / form / input -> executable or interactive content
_ALLOWED_TAGS = {
    "p", "br", "hr",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "ul", "ol", "li", "dl", "dt", "dd",
    "strong", "b", "em", "i", "u", "s", "code", "pre", "blockquote",
    "table", "thead", "tbody", "tr", "th", "td",
    "a", "span", "div",
}

# Only hyperlink targets survive; every style/tracking attribute is dropped.
_ALLOWED_ATTRIBUTES = {"a": {"href", "title"}}

# Pathological pages (or an accidental full-site fetch) shouldn't land a
# megabyte in a TEXT column. Real JDs top out around 15k chars.
MAX_JD_CHARS = 40_000

# Below this, whatever we extracted is boilerplate or a JS shell, not a JD.
# Storing it would be worse than NULL: it would satisfy `if job.description`
# and feed noise to Gemini.
MIN_JD_CHARS = 200


def sanitize_html_to_markdown(html: str) -> Optional[str]:
    """
    Sanitize untrusted posting HTML and convert it to Markdown.

    Returns None when the result is too short to be a real description.
    """
    if not html or not html.strip():
        return None

    cleaned = nh3.clean(
        html,
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        link_rel="noopener noreferrer nofollow",
    )

    md = markdownify(cleaned, heading_style="ATX", bullets="-", strip=["a"])

    # markdownify leaves ragged blank lines and NBSPs from CMS content.
    md = md.replace(" ", " ").replace("​", "")
    md = re.sub(r"[ \t]+\n", "\n", md)
    md = re.sub(r"\n{3,}", "\n\n", md)
    md = "\n".join(line.rstrip() for line in md.splitlines()).strip()

    if len(md) < MIN_JD_CHARS:
        return None
    if len(md) > MAX_JD_CHARS:
        md = md[:MAX_JD_CHARS].rsplit("\n", 1)[0] + "\n\n_[description truncated]_"
    return md


def _first_text(html: str, selectors: Iterable[str]) -> Optional[str]:
    """Return the inner HTML of the first matching selector."""
    soup = BeautifulSoup(html, "lxml")
    for selector in selectors:
        el = soup.select_one(selector)
        if el:
            inner = el.decode_contents()
            if inner and inner.strip():
                return inner
    return None


# ── Per-source extractors ───────────────────────────────────────────────────

async def _from_linkedin(external_id: str) -> Optional[str]:
    """
    LinkedIn's unauthenticated guest endpoint returns the posting
    server-rendered, so no login cookie or browser is needed.
    """
    url = f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{external_id}"
    html = await http_scraper.fetch_page(url)
    if not html:
        return None
    inner = _first_text(
        html,
        (
            ".show-more-less-html__markup",   # tightest: the description body
            ".description__text",
            "section.description",
        ),
    )
    return sanitize_html_to_markdown(inner) if inner else None


def _greenhouse_ids(apply_url: str) -> Optional[tuple]:
    """(board, job_id) from a Greenhouse URL, including the embed form."""
    parsed = urlparse(apply_url)
    m = re.search(r"^/([^/]+)/jobs/(\d+)", parsed.path)
    if m and m.group(1) != "embed":
        return m.group(1), m.group(2)
    # boards.greenhouse.io/embed/job_app?for=<board>&token=<id> (also on
    # job-boards.greenhouse.io); the old regex required "/jobs/" and missed it.
    qs = parse_qs(parsed.query)
    if parsed.path.startswith("/embed/") and qs.get("for") and qs.get("token"):
        return qs["for"][0], qs["token"][0]
    return None


async def _from_greenhouse(apply_url: str) -> Optional[str]:
    ids = _greenhouse_ids(apply_url)
    if not ids:
        return None
    api = f"https://boards-api.greenhouse.io/v1/boards/{ids[0]}/jobs/{ids[1]}"
    raw = await http_scraper.fetch_page(api)
    if not raw:
        return None
    try:
        # Greenhouse returns `content` as HTML-escaped markup.
        content = json.loads(raw).get("content") or ""
    except json.JSONDecodeError:
        return None
    return sanitize_html_to_markdown(unescape(content))


async def _from_lever(apply_url: str) -> Optional[str]:
    m = re.search(r"lever\.co/([^/?]+)/([0-9a-fA-F-]{36})", apply_url)
    if not m:
        return None
    api = f"https://api.lever.co/v0/postings/{m.group(1)}/{m.group(2)}"
    raw = await http_scraper.fetch_page(api)
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    # `description` is the intro and `additional` the closing notes; the
    # responsibilities/requirements bullets live in `lists`, which used to be
    # dropped — leaving most Lever JDs without their actual requirements.
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


# An Ashby board returns every posting for the org in one response, and a
# README lists many roles per company, so cache boards briefly per process.
_ashby_boards: TTLCache = TTLCache(maxsize=256, ttl=600)


async def _from_ashby(apply_url: str) -> Optional[str]:
    # jobs.ashbyhq.com/<org>/<job-uuid>[/application]
    m = re.search(r"ashbyhq\.com/([^/?#]+)/([0-9a-fA-F-]{36})", apply_url)
    if not m:
        return None
    org, job_id = m.group(1), m.group(2).lower()
    jobs = _ashby_boards.get(org)
    if jobs is None:
        raw = await http_scraper.fetch_page(
            f"https://api.ashbyhq.com/posting-api/job-board/{org}",
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
    """
    <tenant>.wdN.myworkdayjobs.com/[<locale>/]<site>/job/<path> maps to the
    CXS JSON endpoint /wday/cxs/<tenant>/<site>/job/<path>. Undocumented but
    it is what Workday's own SPA calls.
    """
    parsed = urlparse(apply_url)
    host_m = re.match(r"^([^.]+)\.wd\d+\.myworkdayjobs\.com$", parsed.netloc.lower())
    if not host_m:
        return None
    segments = [seg for seg in parsed.path.split("/") if seg]
    if segments and re.fullmatch(r"[a-z]{2}-[A-Z]{2}", segments[0]):
        segments = segments[1:]
    if len(segments) < 3 or segments[1] != "job":
        return None
    site, rest = segments[0], "/".join(segments[2:])
    api = f"https://{parsed.netloc}/wday/cxs/{host_m.group(1)}/{site}/job/{rest}"
    raw = await http_scraper.fetch_page(api, headers={"Accept": "application/json"})
    if not raw:
        return None
    try:
        info = json.loads(raw).get("jobPostingInfo") or {}
    except json.JSONDecodeError:
        return None
    return sanitize_html_to_markdown(info.get("jobDescription") or "")


async def _from_smartrecruiters(apply_url: str) -> Optional[str]:
    # jobs.smartrecruiters.com/<Company>/<postingId>-<slug>
    m = re.search(r"smartrecruiters\.com/([^/?#]+)/(\d+)", apply_url)
    if not m:
        return None
    api = f"https://api.smartrecruiters.com/v1/companies/{m.group(1)}/postings/{m.group(2)}"
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
    """
    schema.org/JobPosting carries `description` as escaped HTML. Ashby,
    Workday and many custom boards emit it even when the DOM is JS-rendered,
    which makes this the single highest-yield generic strategy.
    """
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


async def _from_generic(apply_url: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Fallback for the long tail of career hosts: try JSON-LD first, then
    readability's main-content heuristic. Returns (markdown, strategy).
    """
    html = await http_scraper.fetch_page(apply_url)
    if not html:
        return None, None

    via_jsonld = await _from_jsonld(html)
    if via_jsonld:
        return via_jsonld, "jsonld"

    try:
        from readability import Document

        summary_html = Document(html).summary(html_partial=True)
    except Exception as exc:  # readability raises on fragments/empty docs
        logger.debug("readability failed for %s: %s", apply_url, exc)
        return None, None
    md = sanitize_html_to_markdown(summary_html)
    return (md, "readability") if md else (None, None)


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
    """
    Fetch and sanitize the full job description as Markdown.

    Returns (markdown, strategy), where strategy names the extractor that
    produced it (e.g. "greenhouse", "jsonld", "readability"). (None, None)
    when the description cannot be recovered (blocked, JS-only page, or
    extracted text below MIN_JD_CHARS). Callers must treat None as
    "unknown", never as "empty" — leaving the column NULL is correct, and
    lets a later backfill retry.
    """
    try:
        if source == "linkedin" and external_id:
            md = await _from_linkedin(external_id)
            return (md, "linkedin") if md else (None, None)

        if not apply_url:
            return None, None

        host = (urlparse(apply_url).netloc or "").lower()
        for needle, handler in _ATS_DISPATCH:
            if needle in host:
                md = await handler(apply_url)
                if md:
                    return md, handler.__name__.removeprefix("_from_")
                break  # ATS matched but yielded nothing; try the generic path

        return await _from_generic(apply_url)
    except Exception as exc:
        # One bad posting must never abort a whole crawl batch.
        logger.warning("JD extraction failed for %s (%s): %s", apply_url, source, exc)
        return None, None


async def fetch_jd(
    apply_url: str,
    source: str,
    external_id: Optional[str] = None,
) -> Optional[str]:
    """Markdown-only convenience wrapper around fetch_jd_with_source."""
    md, _ = await fetch_jd_with_source(apply_url, source, external_id)
    return md


async def enrich_with_descriptions(
    records: List[Dict[str, Any]],
    concurrency: int = 4,
    min_delay: float = 0.6,
    max_delay: float = 1.6,
) -> int:
    """
    Populate `description` on scraped job dicts, in place.

    Politeness is deliberate, not incidental: this turns one request per crawl
    into one request per *job*, so a semaphore bounds parallelism and each
    task jitters before firing. At concurrency=4 with ~1s jitter, ~125
    LinkedIn jobs take roughly 1-2 minutes rather than hammering the host.

    Returns the number of records that gained a description.
    """
    semaphore = asyncio.Semaphore(concurrency)
    filled = 0

    async def one(record: Dict[str, Any]) -> None:
        nonlocal filled
        if record.get("description"):
            return
        async with semaphore:
            await asyncio.sleep(random.uniform(min_delay, max_delay))
            md, strategy = await fetch_jd_with_source(
                apply_url=record.get("apply_url") or "",
                source=str(record.get("source") or ""),
                external_id=(
                    str(record["external_id"]) if record.get("external_id") else None
                ),
            )
        if md:
            record["description"] = md
            record["description_source"] = strategy
            filled += 1

    await asyncio.gather(*(one(r) for r in records), return_exceptions=True)
    logger.info("JD extraction: %d/%d records gained a description", filled, len(records))
    return filled
