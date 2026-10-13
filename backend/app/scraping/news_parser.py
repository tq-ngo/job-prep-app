import logging
import re
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.news import NewsArticle
from app.ai.gemini_client import (
    generate_text,
    GeminiConfigError,
    GeminiTransientError,
    GeminiTruncatedError,
)
from app.core.datetime_utils import as_utc, utc_now
from app.scraping.dedup import dedup_engine

logger = logging.getLogger(__name__)

# A stored article younger than this is not re-fetched or re-summarized.
# The daily LinkedIn crawl used to re-summarize every known story on every
# run, spending Gemini quota the job enrichment pipeline needed.
ARTICLE_FRESH_FOR = timedelta(days=7)


def article_url_hash(url: str) -> Tuple[str, str]:
    """
    (canonical_url, sha256) for an article URL.

    Hashing the RAW url stored one row per tracking-param variant
    (LinkedIn appends ?trk=... to every link).
    """
    canonical = dedup_engine.canonicalize_url(url)
    return canonical, hashlib.sha256(canonical.encode()).hexdigest()


async def find_article(url: str, session: AsyncSession) -> Optional[NewsArticle]:
    _, url_sha256 = article_url_hash(url)
    result = await session.execute(
        select(NewsArticle).where(NewsArticle.url_sha256 == url_sha256)
    )
    return result.scalar_one_or_none()


def is_fresh(article: Optional[NewsArticle]) -> bool:
    """True when a stored article needs neither a re-fetch nor a summary."""
    return bool(
        article
        and article.enriched_at
        and as_utc(article.scraped_at) > utc_now() - ARTICLE_FRESH_FOR
    )


def extractive_summary(title: str, content: str) -> Tuple[str, List[str], List[str]]:
    """No-AI fallback: first sentences plus keyword-derived categories."""
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if len(s.strip()) > 20]
    fallback_summary = " ".join(sentences[:2]) if sentences else content[:250]
    if len(fallback_summary) > 300:
        fallback_summary = fallback_summary[:297] + "..."

    # Heuristic category tags from text
    lower_content = (title + " " + content).lower()
    fallback_cats = ["Tech"]
    fallback_tags = []
    if any(k in lower_content for k in ["ai", "llm", "gpt", "model", "machine learning"]):
        fallback_cats.append("AI")
        fallback_tags.append("LLM")
    if any(k in lower_content for k in ["security", "hack", "breach", "cyber", "vulnerability"]):
        fallback_cats.append("Security")
        fallback_tags.append("Cybersecurity")
    if any(k in lower_content for k in ["cloud", "aws", "azure", "gcp", "kubernetes"]):
        fallback_cats.append("Cloud")
    if any(k in lower_content for k in ["startup", "funding", "series a", "venture", "vc"]):
        fallback_cats.append("Startups")

    return fallback_summary or "Article content analyzed.", list(set(fallback_cats))[:4], list(set(fallback_tags))[:4]


async def summarize_with_ai(
    title: str, content: str, fallback_on_transient: bool = True
) -> Tuple[str, List[str], List[str]]:
    """
    Use Gemini AI to summarize news article and assign categories and skill/tech tags.

    With fallback_on_transient=False a 429/503 propagates as
    GeminiTransientError, so a Celery task can retry later instead of
    settling for the extractive summary.
    """
    if not content or len(content) < 50:
        return "No sufficient content to summarize.", ["News"], ["Tech"]
        
    prompt = f"""
Article Title: {title}
Article Content (excerpt):
{content[:3500]}

Please provide:
1. A concise, professional 2-sentence executive summary of this technology/industry news, followed by 2-3 structured key takeaway bullets.
2. An array of 2 to 4 relevant category tags (e.g., ["AI", "Startups", "Enterprise", "Cybersecurity", "Cloud"]).
3. An array of 2 to 4 relevant technology or skill tags mentioned (e.g., ["PyTorch", "Kubernetes", "CUDA", "TypeScript"]).

Return ONLY valid JSON in this format:
{{"summary": "...", "categories": ["..."], "tags": ["..."]}}
"""
    try:
        response_text = await generate_text(
            prompt=prompt,
            system_instruction="You are an expert technical news analyst. Output strict JSON only.",
            temperature=0.2,
            max_tokens=1024
        )
        clean = response_text.strip()
        clean = re.sub(r'^```json\s*', '', clean)
        clean = re.sub(r'\s*```$', '', clean)
        
        data = json.loads(clean)
        summary = str(data.get("summary", "")).strip()
        categories = [str(c).strip() for c in data.get("categories", []) if c]
        tags = [str(t).strip() for t in data.get("tags", []) if t]
        if summary and categories:
            return summary, categories[:4], tags[:4]
    except (GeminiConfigError, GeminiTruncatedError):
        # Deployment fault or truncated output. Do NOT silently degrade to the
        # extractive summary — that hid a total Gemini outage behind
        # plausible-looking output, and only at DEBUG level.
        raise
    except GeminiTransientError as e:
        if not fallback_on_transient:
            raise
        logger.warning(f"Gemini transient error for {title!r}, using extractive fallback: {e}")
    except Exception as e:
        # Genuine per-article failure (malformed JSON, safety block, timeout):
        # the extractive fallback below is the correct response.
        logger.warning(f"AI summarization failed for {title!r}, using extractive fallback: {e}")

    return extractive_summary(title, content)

def extract_article_metadata(url: str, html: str) -> Dict[str, Any]:
    """
    Parse HTML using BeautifulSoup to extract clean title, content, author, and date.
    """
    soup = BeautifulSoup(html, "lxml")
    
    # 1. Title extraction (prefer open graph / twitter meta over raw title tag to avoid site name suffixes)
    title = None
    for selector in [
        "meta[property='og:title']",
        "meta[name='twitter:title']",
        "meta[name='title']"
    ]:
        tag = soup.select_one(selector)
        if tag and tag.get("content"):
            title = tag["content"].strip()
            break
            
    if not title:
        for selector in ["h1.article-title", "h1.entry-title", "h1", "title"]:
            tag = soup.select_one(selector)
            if tag:
                title = tag.get_text(strip=True)
                break
                
    if title:
        # Remove common site title suffixes like " | TechCrunch" or " - The Verge"
        title = re.split(r'\s+[|\-–—]\s+(?=[A-Z0-9])', title)[0].strip()
    else:
        # Fallback to URL slug
        slug = urlparse(url).path.strip("/").split("/")[-1]
        title = slug.replace("-", " ").replace("_", " ").title() or "Technology News Article"
        
    # 2. Author extraction
    author = None
    for selector in [
        "meta[name='author']",
        "meta[property='article:author']",
        ".author-name", ".byline", "[rel='author']"
    ]:
        tag = soup.select_one(selector)
        if tag:
            author = tag.get("content") if tag.name == "meta" else tag.get_text(strip=True)
            if author:
                author = author.replace("By ", "").replace("by ", "").strip()
                break
                
    # 3. Published date extraction. Unknown stays None: defaulting to "now"
    # made every undated article look like breaking news at the top of the feed.
    published_at = None
    for selector in [
        "meta[property='article:published_time']",
        "meta[name='pubdate']",
        "meta[name='date']",
        "time[datetime]"
    ]:
        tag = soup.select_one(selector)
        if tag:
            date_str = tag.get("content") or tag.get("datetime")
            if date_str:
                try:
                    # Clean ISO format strings
                    date_str = re.sub(r'\.\d+', '', date_str.split('T')[0] if 'T' in date_str else date_str)
                    published_at = as_utc(
                        datetime.strptime(date_str[:10], "%Y-%m-%d")
                    )
                    break
                except Exception:
                    pass
                    
    # 4. Clean content body extraction
    for tag in soup.find_all(["nav", "footer", "aside", "script", "style", "noscript", "svg", "header", "form"]):
        tag.decompose()
        
    content_paragraphs = []
    container = soup.select_one("article, .article-body, .entry-content, .post-content, main") or soup.body or soup
    for p in container.find_all("p"):
        txt = p.get_text(strip=True)
        if len(txt) > 25 and not any(skip in txt.lower() for skip in ["subscribe", "sign up", "cookie", "copyright", "all rights reserved"]):
            content_paragraphs.append(txt)
            
    content_clean = "\n\n".join(content_paragraphs)
    if not content_clean or len(content_clean) < 100:
        content_clean = container.get_text(separator=" ", strip=True)[:5000]
        
    # 5. Extractive meta description as initial summary
    meta_desc = None
    for selector in ["meta[property='og:description']", "meta[name='twitter:description']", "meta[name='description']"]:
        tag = soup.select_one(selector)
        if tag and tag.get("content"):
            meta_desc = tag["content"].strip()
            break
            
    return {
        "url": url,
        "title": title[:250],
        "author": author[:100] if author else None,
        "published_at": published_at,
        "content_clean": content_clean[:50000],
        "meta_desc": meta_desc,
        "source_domain": urlparse(url).netloc
    }

async def process_and_save_article(url: str, html: str, session: AsyncSession) -> Optional[NewsArticle]:
    """
    Extract metadata and save or update the article. Does NOT summarize.

    Summarization is the rate-limited `summarize_article` Celery task
    (queue "ai"); the caller enqueues it when `article.enriched_at` is None.
    Until then `summary` holds the page's own meta description, and the UI
    marks it as pending.
    """
    canonical, url_sha256 = article_url_hash(url)
    existing = await find_article(canonical, session)
    if is_fresh(existing):
        return existing

    meta = extract_article_metadata(canonical, html)

    if existing:
        existing.title = meta["title"]
        existing.author = meta["author"]
        existing.content_clean = meta["content_clean"]
        existing.published_at = existing.published_at or meta["published_at"]
        if not existing.summary:
            existing.summary = meta["meta_desc"]
        existing.scraped_at = utc_now()
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        logger.info(f"Updated existing news article: {existing.title}")
        return existing

    article = NewsArticle(
        url=canonical,
        url_sha256=url_sha256,
        title=meta["title"],
        author=meta["author"],
        published_at=meta["published_at"],
        content_clean=meta["content_clean"],
        content_raw=meta["content_clean"],
        summary=meta["meta_desc"],
        source_domain=meta["source_domain"],
    )
    session.add(article)
    await session.commit()
    await session.refresh(article)
    logger.info(f"Saved new news article: {article.title}")
    return article
