import asyncio
import logging
import os
import random
import re
import time
import uuid
from datetime import datetime, timedelta
from typing import Optional

from pydantic import ValidationError
from sqlalchemy import String, all_, bindparam, func, text, update
from sqlalchemy.dialects.postgresql import ARRAY
from sqlmodel import select

from app.ai.embedder import generate_embedding
from app.ai.gemini_client import (
    GeminiConfigError,
    GeminiThrottled,
    GeminiTransientError,
    GeminiTruncatedError,
    acquire_gemini_slots,
    set_daily_quota_cooldown,
)
from app.ai.skill_extractor import extract_job_attributes
from app.config import settings
from app.core.database import create_worker_session_ctx
from app.core.datetime_utils import as_utc, utc_now
from app.core.events import KIND_ENRICHED, job_event_payload, publish_job_event
from app.core.locks import acquire_lock, release_lock
from app.core.redis import create_worker_cache_redis, create_worker_redis
from app.models.job import Job
from app.schemas.job import JobCreate
from app.scraping.db_sync import DatabaseSyncService, invalidate_jobs_count_cache
from app.scraping.jd_extractor import enrich_with_descriptions
from app.scraping.parsers.github import parse_github_jobs
from app.scraping.parsers.linkedin import LinkedInScraper
from app.scraping.sponsorship import classify_sponsorship
from app.tasks.celery_app import celery_app
from app.tasks.runtime import HARD_LIMIT_GRACE, run_async

logger = logging.getLogger(__name__)

SCRAPE_TIMEOUT = 3300
SCRAPE_LOCK_TTL_SECONDS = 3600
BACKFILL_TIMEOUT = 1500
BACKFILL_LOCK_TTL_SECONDS = BACKFILL_TIMEOUT + 300

CALLS_PER_ENRICHMENT = 2
QUEUE_DEPTH_MINUTES = 2
STUCK_AFTER_MINUTES = 60
LINKEDIN_STALE_AFTER_DAYS = 21


def _tasks_per_minute(rate: str) -> float:
    """Parse a Celery rate limit ("2/m", "30/h", "1/s", or bare "5" = per second)."""
    match = re.fullmatch(r"\s*(\d+(?:\.\d+)?)\s*(?:/\s*([smh]))?\s*", rate or "")
    if not match:
        return 1.0
    count = float(match.group(1))
    per = {"s": 1 / 60, "m": 1, "h": 60}[match.group(2) or "s"]
    return count / per


async def _publish_job_event(redis, job: Job, skills: list) -> None:
    await publish_job_event(redis, job_event_payload(job, KIND_ENRICHED, skills))


async def deactivate_unseen_github(
    db_service: DatabaseSyncService, source_urls: list, seen_external_ids: list
) -> int:
    stmt = (
        update(Job)
        .where(Job.source == "github")
        .where(Job.source_url.in_(source_urls))
        .where(Job.external_id != all_(
            bindparam("seen_ids", seen_external_ids, type_=ARRAY(String))
        ))
        .where(Job.is_active == True)  # noqa: E712
        .values(is_active=False)
        .returning(Job.canonical_hash)
    )
    deactivated = (await db_service.session.execute(stmt)).scalars().all()
    await db_service.relink_hashes({h for h in deactivated if h})
    return len(deactivated)


@celery_app.task(
    name="app.tasks.job_tasks.scrape_github",
    bind=True,
    max_retries=3,
    queue="scraping",
    time_limit=SCRAPE_TIMEOUT + HARD_LIMIT_GRACE,
)
def scrape_github(self):
    return run_async(_scrape_github, self, self.request.id, timeout=SCRAPE_TIMEOUT)


async def _scrape_github(self, task_id: str = None):
    logger.info("[%s] Starting Github scrape", task_id or self.request.id)

    redis = create_worker_redis()
    cache_redis = create_worker_cache_redis()
    lock_key = "scrape_lock:github"

    lock_token = await acquire_lock(redis, lock_key, SCRAPE_LOCK_TTL_SECONDS)
    if not lock_token:
        logger.info("[%s] GitHub scrape already running — skipping (lock held)", task_id)
        await redis.aclose(close_connection_pool=True)
        await cache_redis.aclose(close_connection_pool=True)
        return {"status": "skipped", "reason": "lock_held"}

    try:
        start_time = time.monotonic()
        total_stats = {
            "inserted": 0, "updated": 0, "skipped": 0, "linked": 0,
            "descriptions": 0, "source": "github",
        }

        async with create_worker_session_ctx() as session:
            db_service = DatabaseSyncService(session)
            batch = []

            job_gen, successful_urls = await parse_github_jobs()
            seen_external_ids = []

            async def flush(records):
                result = await db_service.sync_batch(records, enrich_with_descriptions)
                for key in total_stats:
                    if key in result:
                        total_stats[key] += result[key]

            for job in job_gen:
                batch.append(job.model_dump())
                seen_external_ids.append(job.external_id)

                if len(batch) >= 150:
                    await flush(batch)
                    batch.clear()

            await flush(batch)

            if successful_urls and seen_external_ids:
                total_stats["deactivated"] = await deactivate_unseen_github(
                    db_service, successful_urls, seen_external_ids
                )
                if total_stats["deactivated"]:
                    await invalidate_jobs_count_cache(cache_redis)
            await session.commit()

        duration = time.monotonic() - start_time
        logger.info("GitHub complete in %.1fs: %s", duration, total_stats)
        return total_stats
    except Exception as exc:
        logger.error("GitHub scrape failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose(close_connection_pool=True)
        await cache_redis.aclose(close_connection_pool=True)


@celery_app.task(
    name="app.tasks.job_tasks.scrape_linkedin",
    bind=True,
    max_retries=1,
    queue="scraping",
    time_limit=SCRAPE_TIMEOUT + HARD_LIMIT_GRACE,
)
def scrape_linkedin(self, search_url: str):
    return run_async(_scrape_linkedin, self, search_url, self.request.id, timeout=SCRAPE_TIMEOUT)


async def _scrape_linkedin(self, search_url: str, task_id: str = None):
    logger.info("[%s] Starting LinkedIn scrape for %s", task_id or self.request.id, search_url)
    redis = create_worker_redis()
    lock_key = "scrape_lock:linkedin"

    lock_token = await acquire_lock(redis, lock_key, SCRAPE_LOCK_TTL_SECONDS)
    if not lock_token:
        logger.info("[%s] LinkedIn scrape already running — skipping (lock held)", task_id)
        await redis.aclose(close_connection_pool=True)
        return {"status": "skipped", "reason": "lock_held"}

    li_at = os.getenv("LINKEDIN_LI_AT", "")

    async def progress_tracker(percent: int, message: str):
        self.update_state(
            state="PROGRESS",
            meta={"percent": percent, "message": message},
            task_id=task_id or self.request.id,
        )

    try:
        start_time = time.monotonic()
        scraper = LinkedInScraper()
        raw_jobs = await scraper.fetch_jobs(
            base_search_url=search_url,
            li_at_cookie=li_at,
            max_pages=5,
            progress_callback=progress_tracker,
        )

        if not raw_jobs:
            logger.warning("[%s] LinkedIn returned no jobs — possible rate limit or anti-bot block", task_id)
            return {"status": "failed", "reason": "no_jobs_returned"}

        total_stats = {
            "inserted": 0, "updated": 0, "skipped": 0, "linked": 0,
            "descriptions": 0, "source": "linkedin",
        }

        async with create_worker_session_ctx() as session:
            db_service = DatabaseSyncService(session)
            batch = []

            async def flush(records):
                result = await db_service.sync_batch(records, enrich_with_descriptions)
                for key in total_stats:
                    if key in result:
                        total_stats[key] += result[key]

            for job_dict in raw_jobs:
                try:
                    job = JobCreate(**job_dict)
                except ValidationError as exc:
                    logger.debug("Skipping invalid LinkedIn job card: %s", exc)
                    continue
                batch.append(job.model_dump())

                if len(batch) >= 100:
                    await flush(batch)
                    batch.clear()

            await flush(batch)

        duration = time.monotonic() - start_time
        logger.info("LinkedIn complete in %.1fs: %s", duration, total_stats)
        return total_stats

    except Exception as exc:
        logger.error("LinkedIn scrape failed: %s", exc, exc_info=True)
        raise self.retry(exc=exc, countdown=120)

    finally:
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose(close_connection_pool=True)


# ── AI enrichment ────────────────────────────────────────────────────────

def _claimed(stmt, job_id: uuid.UUID, claimed_at: Optional[datetime]):
    stmt = stmt.where(Job.id == job_id, Job.scrape_status == "queued")
    if claimed_at is not None:
        stmt = stmt.where(Job.queued_at == claimed_at)
    return stmt


def _holds_claim(job: Job, claimed_at: Optional[datetime]) -> bool:
    if job.scrape_status != "queued":
        return False
    return claimed_at is None or as_utc(job.queued_at) == claimed_at


async def _end_claim(job_id: uuid.UUID, claimed_at: Optional[datetime], status: str) -> bool:
    """Move a still-claimed job to `status` ('raw' to retry later, 'failed')."""
    async with create_worker_session_ctx() as session:
        result = await session.execute(
            _claimed(update(Job), job_id, claimed_at).values(scrape_status=status, queued_at=None)
        )
        await session.commit()
        return bool(result.rowcount)


@celery_app.task(
    name="app.tasks.job_tasks.enrich_job_with_ai",
    bind=True,
    max_retries=2,
    queue="ai",
    rate_limit=settings.GEMINI_RATE_LIMIT,
)
def enrich_job_with_ai(self, job_id: str, claim: Optional[str] = None):
    return run_async(_enrich_job_with_ai, self, job_id, claim, self.request.id)


async def _enrich_job_with_ai(self, job_id: str, claim: Optional[str] = None, task_id: str = None):
    """
    Celery task: enrich a single job with Gemini AI.

    Read and write DB sessions are deliberately separated around Gemini HTTP
    I/O so Postgres connections are never held `idle in transaction`.
    """
    logger.info("[%s] Enriching job %s", task_id or self.request.id, job_id)
    jid = uuid.UUID(job_id)
    claimed_at = datetime.fromisoformat(claim) if claim else None
    redis = create_worker_redis()

    try:
        # 1. Short read session: load snapshot and close DB connection before Gemini I/O.
        async with create_worker_session_ctx() as session:
            job = await session.get(Job, jid)
            if not job:
                logger.error("Job %s not found", job_id)
                return "missing"
            if not _holds_claim(job, claimed_at):
                logger.info("Job %s is no longer claimed by this task — skipping", job_id)
                return "skipped"
            job_title = job.title
            job_company = job.company
            job_description = job.description
            existing_skills = job.skills
            has_salary = job.salary_min is not None or job.salary_max is not None
            has_seniority = bool(job.seniority_level)
            has_employment = bool(job.employment_type)

        values: dict = {"scrape_status": "enriched", "enriched_at": utc_now(), "queued_at": None}
        skills: list = list(existing_skills or [])

        # 2. External Gemini I/O with NO open Postgres transaction.
        if job_description:
            needs_attrs = not existing_skills
            calls_needed = CALLS_PER_ENRICHMENT if needs_attrs else 1
            await acquire_gemini_slots(redis, calls_needed)

            if needs_attrs:
                attrs = await extract_job_attributes(job_title, job_description)
                skills = attrs.skills
                attr_updates: dict = {"skills": skills}
                if not has_salary and attrs.salary_period:
                    attr_updates.update(
                        salary_min=attrs.salary_min,
                        salary_max=attrs.salary_max,
                        salary_period=attrs.salary_period,
                    )
                if not has_seniority and attrs.seniority_level:
                    attr_updates["seniority_level"] = attrs.seniority_level
                if not has_employment and attrs.employment_type:
                    attr_updates["employment_type"] = attrs.employment_type
                values.update(attr_updates)

                # Checkpoint extracted attributes before embedding so a failure on
                # step 2 never discards step 1's Gemini call.
                async with create_worker_session_ctx() as session:
                    await session.execute(
                        _claimed(update(Job), jid, claimed_at).values(**attr_updates)
                    )
                    await session.commit()

            # Lead with title, company, and skills so truncation keeps high-signal metadata.
            skills_prefix = f"Skills: {', '.join(skills)}. " if skills else ""
            embed_input = f"{job_title} at {job_company}. {skills_prefix}{job_description}"
            embedding = await generate_embedding(embed_input, task_type="RETRIEVAL_DOCUMENT")
            values["embedding"] = embedding

        # 3. Short conditional write session returning the refreshed Job row.
        async with create_worker_session_ctx() as session:
            updated_job = (
                await session.execute(
                    _claimed(update(Job), jid, claimed_at)
                    .values(**values)
                    .returning(Job)
                )
            ).scalar_one_or_none()
            await session.commit()

        if updated_job is None:
            logger.info("Job %s was re-claimed while enriching — result discarded", job_id)
            return "superseded"

        logger.info("Job %s enriched: %d skills", job_id, len(skills))
        if updated_job.is_active and updated_job.canonical_id is None:
            await _publish_job_event(redis, updated_job, skills)
        return "enriched"

    except asyncio.CancelledError:
        # Release claim on task timeout so the row is not stranded for 60m.
        try:
            await _end_claim(jid, claimed_at, "raw")
        except Exception:
            pass
        raise

    except GeminiThrottled as exc:
        await _end_claim(jid, claimed_at, "raw")
        logger.info("Job %s deferred: %s", job_id, exc)
        return "throttled"

    except GeminiConfigError:
        await _end_claim(jid, claimed_at, "raw")
        raise

    except GeminiTruncatedError:
        await _end_claim(jid, claimed_at, "failed")
        raise

    except GeminiTransientError as exc:
        if exc.is_daily_quota:
            await set_daily_quota_cooldown(redis, exc.retry_after or 900)
            await _end_claim(jid, claimed_at, "raw")
            logger.warning("Daily Gemini quota exhausted; cooling down and deferring job %s", job_id)
            return "throttled"
        if self.request.retries >= self.max_retries:
            await _end_claim(jid, claimed_at, "raw")
            raise
        countdown = (exc.retry_after or 30) + random.randint(2, 10)
        raise self.retry(exc=exc, countdown=countdown)

    except Exception as exc:
        logger.error("AI enrichment failed for job %s: %s", job_id, exc)
        if self.request.retries >= self.max_retries:
            await _end_claim(jid, claimed_at, "failed")
            logger.warning("Job %s marked as failed after max retries", job_id)
            raise
        raise self.retry(exc=exc, countdown=30)

    finally:
        await redis.aclose(close_connection_pool=True)


@celery_app.task(
    name="app.tasks.job_tasks.process_raw_jobs_batch",
    bind=True,
    max_retries=1,
    queue="ai",
)
def process_raw_jobs_batch(self, batch_size: int = 10):
    return run_async(_process_raw_jobs_batch, self, batch_size, self.request.id)


async def _process_raw_jobs_batch(self, batch_size: int = 10, task_id: str = None):
    """
    Periodic task: claim newest active canonical 'raw' jobs and enqueue them for AI enrichment.
    """
    logger.info("[%s] Starting AI Enrichment Batch", task_id or self.request.id)

    capacity = max(1, round(_tasks_per_minute(settings.GEMINI_RATE_LIMIT) * QUEUE_DEPTH_MINUTES))

    try:
        async with create_worker_session_ctx() as session:
            queued = (await session.execute(
                select(func.count()).select_from(Job).where(Job.scrape_status == "queued")
            )).scalar_one()
            limit = min(batch_size, capacity - queued)
            if limit <= 0:
                return f"Queue full ({queued} queued)"

            # Prioritize active canonical postings newest-first so fresh listings
            # aren't starved behind old, closed, or duplicate rows.
            claimed = (await session.execute(
                text(
                    """
                    UPDATE jobs SET scrape_status = 'queued', queued_at = NOW()
                    WHERE id IN (
                        SELECT id FROM jobs
                        WHERE scrape_status = 'raw'
                          AND is_active = TRUE
                          AND canonical_id IS NULL
                        ORDER BY first_seen_at DESC
                        LIMIT :limit
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id, queued_at
                    """
                ),
                {"limit": limit},
            )).all()
            await session.commit()

            if not claimed:
                return "No raw jobs found"

            for job_id, queued_at in claimed:
                await asyncio.to_thread(
                    enrich_job_with_ai.delay, str(job_id), as_utc(queued_at).isoformat()
                )

            return f"Enqueued {len(claimed)} jobs for enrichment"

    except Exception as exc:
        logger.error("Batch failed: %s", exc, exc_info=True)
        raise


@celery_app.task(
    name="app.tasks.job_tasks.requeue_stuck_jobs",
    bind=True,
    queue="ai",
)
def requeue_stuck_jobs(self, stale_after_minutes: int = STUCK_AFTER_MINUTES):
    return run_async(_requeue_stuck_jobs, self, stale_after_minutes)


async def _requeue_stuck_jobs(self, stale_after_minutes: int = STUCK_AFTER_MINUTES):
    async with create_worker_session_ctx() as session:
        result = await session.execute(
            text(
                """
                UPDATE jobs SET scrape_status = 'raw', queued_at = NULL
                WHERE scrape_status = 'queued'
                  AND (queued_at IS NULL
                       OR queued_at < NOW() - (:mins || ' minutes')::interval)
                RETURNING id
                """
            ),
            {"mins": stale_after_minutes},
        )
        count = len(result.fetchall())
        await session.commit()
    if count:
        logger.warning("Requeued %d jobs stuck in 'queued'", count)
    return f"Requeued {count}"


@celery_app.task(
    name="app.tasks.job_tasks.deactivate_stale_jobs",
    bind=True,
    queue="default",
)
def deactivate_stale_jobs(self, source: str = "linkedin", max_age_days: int = LINKEDIN_STALE_AFTER_DAYS):
    return run_async(_deactivate_stale_jobs, self, source, max_age_days)


async def _deactivate_stale_jobs(self, source: str, max_age_days: int):
    cutoff = utc_now() - timedelta(days=max_age_days)
    async with create_worker_session_ctx() as session:
        deactivated = (await session.execute(
            update(Job)
            .where(Job.source == source)
            .where(Job.is_active == True)  # noqa: E712
            .where(Job.scraped_at < cutoff)
            .values(is_active=False)
            .returning(Job.canonical_hash)
        )).scalars().all()
        await DatabaseSyncService(session).relink_hashes({h for h in deactivated if h})
        await session.commit()
    if deactivated:
        logger.info("Deactivated %d %s postings unseen for %d days", len(deactivated), source, max_age_days)
        cache_redis = create_worker_cache_redis()
        try:
            await invalidate_jobs_count_cache(cache_redis)
        finally:
            await cache_redis.aclose(close_connection_pool=True)
    return f"Deactivated {len(deactivated)}"


@celery_app.task(
    name="app.tasks.job_tasks.backfill_descriptions",
    bind=True,
    queue="scraping",
    time_limit=BACKFILL_TIMEOUT + HARD_LIMIT_GRACE,
)
def backfill_descriptions(self, batch_size: int = 50):
    return run_async(_backfill_descriptions, self, batch_size, timeout=BACKFILL_TIMEOUT)


async def _backfill_descriptions(self, batch_size: int = 50):
    redis = create_worker_redis()
    lock_key = "scrape_lock:backfill_descriptions"
    lock_token = await acquire_lock(redis, lock_key, BACKFILL_LOCK_TTL_SECONDS)
    if not lock_token:
        logger.info("Backfill already running — skipping (lock held)")
        await redis.aclose(close_connection_pool=True)
        return "skipped (lock held)"

    try:
        async with create_worker_session_ctx() as session:
            rows = (await session.execute(
                select(Job.id, Job.external_id, Job.source, Job.apply_url, Job.title)
                .where(Job.description.is_(None))
                .where(Job.description_fetched_at.is_(None))
                .where(Job.is_active == True)  # noqa: E712
                .order_by(Job.scraped_at.desc())
                .limit(batch_size)
            )).all()
            await session.commit()

        if not rows:
            return "Nothing to backfill"

        records = [
            {
                "external_id": r.external_id,
                "source": r.source,
                "apply_url": r.apply_url,
                "description": None,
            }
            for r in rows
        ]
        filled = await enrich_with_descriptions(records)

        now = utc_now()
        requeued = 0
        async with create_worker_session_ctx() as session:
            for row, record in zip(rows, records):
                values: dict = {"description_fetched_at": now}
                if record.get("description"):
                    spons = classify_sponsorship(row.title or "", record["description"])
                    values.update(
                        description=record["description"],
                        description_source=record.get("description_source"),
                        sponsorship_status=spons["status"],
                        sponsorship_label=spons["label"],
                        scrape_status="raw",
                        queued_at=None,
                    )
                result = await session.execute(
                    update(Job)
                    .where(Job.id == row.id, Job.description.is_(None))
                    .values(**values)
                )
                if record.get("description") and result.rowcount:
                    requeued += 1
            await session.commit()

        logger.info("Backfill: %d/%d rows gained a description", filled, len(rows))
        return f"Backfilled {filled}/{len(rows)}, requeued {requeued} for enrichment"
    finally:
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose(close_connection_pool=True)
