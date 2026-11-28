"""
Live job events, published to a Redis Stream and served by api/v1/sse.py.

Two kinds, both under the SSE event name `job`:

    created   emitted by scraping/db_sync.py right after a posting is first
              inserted — seconds after the crawl sees it.
    enriched  emitted by tasks/job_tasks.py once Gemini has extracted skills.

Events used to be published only after enrichment, which is rate-limited to
~2 jobs/minute, so a 125-job crawl reached the "live" board over about an
hour. `created` restores the real-time path; `enriched` carries the skills
needed for skill-filtered alert streams.
"""
import json

JOBS_STREAM = "jobs:events"
# Bounded so the backlog can't grow without limit. ~10k events is far more
# than any client needs to catch up on after a reconnect.
JOBS_STREAM_MAXLEN = 10_000

KIND_CREATED = "created"
KIND_ENRICHED = "enriched"

NEWS_STREAM = "news:events"
NEWS_STREAM_MAXLEN = 500
NEWS_KIND_CREATED = "created"
NEWS_KIND_SUMMARIZED = "summarized"
NEWS_KIND_PRUNED = "pruned"


async def publish_job_event(redis, payload: dict) -> str:
    """Append an event to the stream. Returns its id."""
    return await redis.xadd(
        JOBS_STREAM,
        {"data": json.dumps(payload)},
        maxlen=JOBS_STREAM_MAXLEN,
        approximate=True,
    )


async def publish_news_event(redis, payload: dict) -> str:
    """Append a news lifecycle event to the news Redis stream."""
    return await redis.xadd(
        NEWS_STREAM,
        {"data": json.dumps(payload)},
        maxlen=NEWS_STREAM_MAXLEN,
        approximate=True,
    )


def news_event_payload(article, kind: str) -> dict:
    """Serialize a NewsArticle row into an SSE event payload."""
    return {
        "kind": kind,
        "id": str(article.id),
        "title": article.title,
        "url": article.url,
        "source_domain": article.source_domain,
        "published_at": article.published_at.isoformat() if getattr(article, "published_at", None) else None,
        "scraped_at": article.scraped_at.isoformat() if getattr(article, "scraped_at", None) else None,
        "summary": article.summary,
        "categories": list(article.categories or []) if article.categories is not None else None,
        "tags": list(article.tags or []) if article.tags is not None else None,
        "enriched_at": article.enriched_at.isoformat() if getattr(article, "enriched_at", None) else None,
    }


def job_event_payload(job, kind: str, skills=None) -> dict:
    """Serialize a Job row (or a row-like object) into an event payload."""
    return {
        "kind": kind,
        "id": str(job.id),
        "title": job.title,
        "company": job.company,
        "company_domain": getattr(job, "company_domain", None),
        "location": job.location,
        "skills": list(skills or (job.skills if hasattr(job, "skills") and job.skills else [])),
        "apply_url": job.apply_url,
        "source": job.source,
        "is_remote": job.is_remote,
        "sponsorship_status": getattr(job, "sponsorship_status", None),
        "sponsorship_label": getattr(job, "sponsorship_label", None),
        "category": getattr(job, "category", None),
        "posted_at": job.posted_at.isoformat() if getattr(job, "posted_at", None) else None,
        "salary_min": getattr(job, "salary_min", None),
        "salary_max": getattr(job, "salary_max", None),
        "salary_currency": getattr(job, "salary_currency", None),
        "salary_period": getattr(job, "salary_period", None),
        "seniority_level": getattr(job, "seniority_level", None),
        "employment_type": getattr(job, "employment_type", None),
        "enriched_at": job.enriched_at.isoformat() if getattr(job, "enriched_at", None) else None,
    }
