import logging
import re
import json
import hashlib
from datetime import datetime
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.news import NewsArticle
from app.ai.gemini_client import generate_text

logger = logging.getLogger(__name__)

async def summarize_with_ai(title: str, content: str) -> Tuple[str, List[str]]:
    """
    Use Gemini AI to summarize news article and assign categories.
    Falls back gracefully if API is unconfigured or errors out.
    """
    if not content or len(content) < 50:
        return "No sufficient content to summarize.", ["News"]
        
    prompt = f"""
Article Title: {title}
Article Content (excerpt):
{content[:3500]}

Please provide:
1. A concise, professional 2-sentence executive summary of this technology/industry news.
2. An array of 2 to 4 relevant category tags (e.g., ["AI", "Startups", "Enterprise", "Cybersecurity", "Cloud"]).

Return ONLY valid JSON in this format:
{{"summary": "...", "categories": ["..."]}}
"""
    try:
        response_text = await generate_text(
            prompt=prompt,
            system_instruction="You are an expert technical news analyst. Output strict JSON only.",
            temperature=0.2,
            max_tokens=300
        )
        clean = response_text.strip()
        clean = re.sub(r'^```json\s*', '', clean)
        clean = re.sub(r'\s*```$', '', clean)
        
        data = json.loads(clean)
        summary = str(data.get("summary", "")).strip()
        categories = [str(c).strip() for c in data.get("categories", []) if c]
        if summary and categories:
            return summary, categories[:4]
    except Exception as e:
        logger.debug(f"AI summarization fallback triggered: {e}")
        
    # Extractive fallback
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', content) if len(s.strip()) > 20]
    fallback_summary = " ".join(sentences[:2]) if sentences else content[:250]
    if len(fallback_summary) > 300:
        fallback_summary = fallback_summary[:297] + "..."
        
    # Heuristic category tags from text
    lower_content = (title + " " + content).lower()
    fallback_cats = ["Tech"]
    if any(k in lower_content for k in ["ai", "llm", "gpt", "model", "machine learning"]):
        fallback_cats.append("AI")
    if any(k in lower_content for k in ["security", "hack", "breach", "cyber", "vulnerability"]):
        fallback_cats.append("Security")
    if any(k in lower_content for k in ["cloud", "aws", "azure", "gcp", "kubernetes"]):
        fallback_cats.append("Cloud")
    if any(k in lower_content for k in ["startup", "funding", "series a", "venture", "vc"]):
        fallback_cats.append("Startups")
        
    return fallback_summary or "Article content analyzed.", list(set(fallback_cats))[:4]

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
                
    # 3. Published date extraction
    published_at = datetime.utcnow()
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
                    published_at = datetime.strptime(date_str[:10], "%Y-%m-%d")
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
    Extract metadata, generate AI summary/categories, and save or update in PostgreSQL.
    """
    url_sha256 = hashlib.sha256(url.encode()).hexdigest()
    
    # Check existing
    stmt = select(NewsArticle).where(NewsArticle.url_sha256 == url_sha256)
    result = await session.execute(stmt)
    existing = result.scalar_one_or_none()
    
    meta = extract_article_metadata(url, html)
    
    # Summarize & Categorize
    summary, categories = await summarize_with_ai(meta["title"], meta["content_clean"] or meta["meta_desc"] or "")
    if not summary and meta["meta_desc"]:
        summary = meta["meta_desc"]
        
    if existing:
        existing.title = meta["title"]
        existing.author = meta["author"]
        existing.content_clean = meta["content_clean"]
        existing.summary = summary
        existing.categories = categories
        existing.scraped_at = datetime.utcnow()
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        logger.info(f"Updated existing news article: {existing.title}")
        return existing
    else:
        article = NewsArticle(
            url=url,
            url_sha256=url_sha256,
            title=meta["title"],
            author=meta["author"],
            published_at=meta["published_at"],
            content_clean=meta["content_clean"],
            content_raw=meta["content_clean"],
            summary=summary,
            categories=categories,
            source_domain=meta["source_domain"]
        )
        session.add(article)
        await session.commit()
        await session.refresh(article)
        logger.info(f"Saved new news article: {article.title}")
        return article
