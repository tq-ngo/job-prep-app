"""
Full job-description extraction and sanitization.

Neither crawler used to fetch a description: parsers/linkedin.py and
parsers/github.py both emitted metadata only, so `jobs.description` was NULL
for every row. That single gap made Gemini skill extraction, pgvector
embeddings, /search/semantic and the UI's job-detail drawer all inert.

This module adds the missing stage. Given a job record it fetches the real
posting body, sanitizes it, and converts it to Markdown for storage:

    LinkedIn  -> /jobs-guest/jobs/api/jobPosting/{id}   (server-rendered)
    Greenhouse-> boards-api.greenhouse.io/v1/boards/... (clean JSON)
    Lever     -> api.lever.co/v0/postings/...           (clean JSON)
    Ashby     -> embedded JSON-LD / __NEXT_DATA__, else generic
    other     -> readability-lxml main-content extraction

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
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

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


async def _from_greenhouse(apply_url: str) -> Optional[str]:
    m = re.search(r"greenhouse\.io/(?:embed/job_app\?for=)?([^/?&]+)/jobs/(\d+)", apply_url)
    if not m:
        return None
    api = f"https://boards-api.greenhouse.io/v1/boards/{m.group(1)}/jobs/{m.group(2)}"
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
    # `description` is the intro; `descriptionBody`/`additional` hold the
    # requirements. Concatenate the HTML variants so nothing is dropped.
    parts = [data.get("description") or "", data.get("additional") or ""]
    combined = "\n".join(p for p in parts if p)
    return sanitize_html_to_markdown(combined)


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


async def _from_generic(apply_url: str) -> Optional[str]:
    """
    Fallback for the long tail of career hosts: try JSON-LD first, then
    readability's main-content heuristic.
    """
    html = await http_scraper.fetch_page(apply_url)
    if not html:
        return None

    via_jsonld = await _from_jsonld(html)
    if via_jsonld:
        return via_jsonld

    try:
        from readability import Document

        summary_html = Document(html).summary(html_partial=True)
    except Exception as exc:  # readability raises on fragments/empty docs
        logger.debug("readability failed for %s: %s", apply_url, exc)
        return None
    return sanitize_html_to_markdown(summary_html)


# ── Public API ──────────────────────────────────────────────────────────────

_ATS_DISPATCH = (
    ("greenhouse.io", _from_greenhouse),
    ("lever.co", _from_lever),
)


async def fetch_jd(
    apply_url: str,
    source: str,
    external_id: Optional[str] = None,
) -> Optional[str]:
    """
    Fetch and sanitize the full job description as Markdown.

    Returns None when the description cannot be recovered (blocked, JS-only
    page, or extracted text below MIN_JD_CHARS). Callers must treat None as
    "unknown", never as "empty" — leaving the column NULL is correct, and
    lets a later backfill retry.
    """
    try:
        if source == "linkedin" and external_id:
            return await _from_linkedin(external_id)

        if not apply_url:
            return None

        host = (urlparse(apply_url).netloc or "").lower()
        for needle, handler in _ATS_DISPATCH:
            if needle in host:
                md = await handler(apply_url)
                if md:
                    return md
                break  # ATS matched but yielded nothing; try the generic path

        return await _from_generic(apply_url)
    except Exception as exc:
        # One bad posting must never abort a whole crawl batch.
        logger.warning("JD extraction failed for %s (%s): %s", apply_url, source, exc)
        return None


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
            md = await fetch_jd(
                apply_url=record.get("apply_url") or "",
                source=str(record.get("source") or ""),
                external_id=(
                    str(record["external_id"]) if record.get("external_id") else None
                ),
            )
        if md:
            record["description"] = md
            filled += 1

    await asyncio.gather(*(one(r) for r in records), return_exceptions=True)
    logger.info("JD extraction: %d/%d records gained a description", filled, len(records))
    return filled
