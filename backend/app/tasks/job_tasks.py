import logging
import random
from datetime import datetime, timezone
import json
import uuid
import os

from sqlmodel import select
from sqlalchemy import text, update

from app.tasks.celery_app import celery_app
from app.scraping.parsers.github import parse_github_jobs
from app.scraping.db_sync import DatabaseSyncService
from app.scraping.jd_extractor import enrich_with_descriptions
from app.core.database import create_worker_session, create_worker_session_ctx
from app.core.datetime_utils import utc_now
from app.models.job import Job
from app.ai.skill_extractor import extract_skills
from app.ai.embedder import generate_embedding
from app.core.redis import create_worker_redis
from app.api.v1.sse import publish_job_event
from app.config import settings
from app.schemas.job import JobCreate
from app.scraping.parsers.linkedin import LinkedInScraper

logger = logging.getLogger(__name__)


async def _publish_job_event(job: Job, skills: list) -> None:
    """
    Publish a new-job event for the SSE hub.

    Factored out of two near-identical inline blocks that each created a fresh
    Redis client and never closed it.
    """
    redis = create_worker_redis()
    try:
        # Redis Stream, not pub/sub: pub/sub had no backlog, so any event
        # published while a client was reconnecting was lost forever.
        await publish_job_event(redis, {
            "id": str(job.id),
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "skills": skills,
            "apply_url": job.apply_url,
            "source": job.source,
            "is_remote": job.is_remote,
        })
    finally:
        await redis.aclose()

@celery_app.task(
    name="app.tasks.job_tasks.scrape_github",
    bind=True,
    max_retries=3,
    queue="scraping",
)
def scrape_github(self):
    from asgiref.sync import async_to_sync
    return async_to_sync(_scrape_github)(self, self.request.id)

async def _scrape_github(self, task_id: str = None):
    """
    Celery task: scrape internship listings from GitHub repos
    """
    logger.info(f"[{task_id or self.request.id}] Starting Github scrape")
    
    redis = create_worker_redis()
    lock_key = "scrape_lock:github"
    scrape_start_time = datetime.now(timezone.utc)

    # Acquire the lock inside the async body so it applies to
    # BOTH API-triggered and Beat-triggered runs.
    lock_acquired = await redis.set(lock_key, "locked", nx=True, ex=600)
    if not lock_acquired:
        logger.info(f"[{task_id}] GitHub scrape already running — skipping (lock held)")
        return {"status": "skipped", "reason": "lock_held"}
    
    try:
        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "linked": 0,
                       "descriptions": 0, "source": "github"}

        async with create_worker_session_ctx() as session:
            db_service = DatabaseSyncService(session)
            batch = []

            job_gen, successful_urls = await parse_github_jobs()
            seen_external_ids = []

            async def flush(records):
                if not records:
                    return
                # Fetch the real JD before upserting. GitHub READMEs are just
                # link tables, so the description lives behind apply_url on
                # the ATS (Greenhouse/Lever/Ashby/...).
                total_stats["descriptions"] += await enrich_with_descriptions(records)
                for r in records:
                    if r.get("description"):
                        r["description_fetched_at"] = utc_now()
                result = await db_service.bulk_upsert_jobs(records)
                for key in ("inserted", "updated", "skipped", "linked"):
                    total_stats[key] += result[key]

            for job in job_gen:
                batch.append(job.model_dump())
                seen_external_ids.append(job.external_id)

                if len(batch) >= 100:
                    await flush(batch)
                    batch.clear()

            await flush(batch)
            
            # Mark stale jobs inactive: any GitHub job from a successfully-crawled
            # source that is NO LONGER in the current batch was removed from the
            # README and should be hidden from the UI.
            #
            # BUG FIX: The old logic used `source_url.in_(successful_urls)` +
            # `scraped_at < scrape_start_time`. Since source_url = README raw URL
            # (not the apply URL), this matched ALL GitHub jobs from those repos.
            # And since dedup hits don't update scraped_at, EVERY existing job
            # was silently deactivated on re-run. Fixed by comparing external_ids.
            if successful_urls and seen_external_ids:
                stmt = (
                    update(Job)
                    .where(Job.source == "github")
                    .where(Job.source_url.in_(successful_urls))
                    .where(Job.external_id.notin_(seen_external_ids))
                    .values(is_active=False)
                )
                await session.execute(stmt)
            await session.commit()
            
        logger.info(f"GitHub complete: {total_stats}")
        return total_stats
    except Exception as exc:
        logger.error(f"GitHub scrape failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        # C4 FIX: Only release the lock if THIS task acquired it.
        # Previously the finally always deleted the key — on a Beat-triggered
        # run (no lock) this silently deleted a lock held by a concurrent
        # API-triggered run, unblocking it prematurely.
        if lock_acquired:
            await redis.delete(lock_key)


@celery_app.task(
    name="app.tasks.job_tasks.scrape_linkedin",
    bind=True,
    max_retries=1,
    queue="scraping",
)
def scrape_linkedin(self, search_url: str):
    from asgiref.sync import async_to_sync
    return async_to_sync(_scrape_linkedin)(self, search_url, self.request.id)

async def _scrape_linkedin(self, search_url: str, task_id: str = None):
    """
    Celery task: sequentially scrape LinkedIn job pages
    """
    logger.info(f"[{task_id or self.request.id}] Starting LinkedIn scrape for {search_url}")
    redis = create_worker_redis()
    lock_key = "scrape_lock:linkedin"
    
    # C5 FIX: Acquire the lock inside the async body so Beat-triggered
    # runs are also protected. If the API handler already set the lock,
    # we skip rather than running a duplicate scrape.
    lock_acquired = await redis.set(lock_key, "locked", nx=True, ex=600)
    if not lock_acquired:
        logger.info(f"[{task_id}] LinkedIn scrape already running — skipping (lock held)")
        return {"status": "skipped", "reason": "lock_held"}

    # Optional: fetch from DB/Redis instead of env
    li_at = os.getenv("LINKEDIN_LI_AT", "")

    # Progress callback mapping directly to Celery task state
    async def progress_tracker(percent: int, message: str):
        self.update_state(
            state='PROGRESS',
            meta={'percent': percent, 'message': message},
            task_id=task_id or self.request.id
        )

    try:
        scraper = LinkedInScraper()
        raw_jobs = await scraper.fetch_jobs(
            base_search_url=search_url,
            li_at_cookie=li_at,
            max_pages=5,
            progress_callback=progress_tracker
        )
        
        if not raw_jobs:
            logger.warning(f"[{task_id}] LinkedIn returned no jobs — possible rate limit or anti-bot block")
            return {"status": "failed", "reason": "no_jobs_returned"}

        total_stats = {"inserted": 0, "updated": 0, "skipped": 0, "linked": 0,
                       "descriptions": 0, "source": "linkedin"}

        async with create_worker_session_ctx() as session:
            db_service = DatabaseSyncService(session)
            batch = []

            async def flush(records):
                if not records:
                    return
                # One extra request per job against LinkedIn's guest detail
                # endpoint. enrich_with_descriptions bounds concurrency and
                # jitters between calls to stay polite.
                total_stats["descriptions"] += await enrich_with_descriptions(records)
                for r in records:
                    if r.get("description"):
                        r["description_fetched_at"] = utc_now()
                result = await db_service.bulk_upsert_jobs(records)
                for key in ("inserted", "updated", "skipped", "linked"):
                    total_stats[key] += result[key]

            for job_dict in raw_jobs:
                job = JobCreate(**job_dict)
                batch.append(job.model_dump())

                # Sync in chunks of 50 to respect memory and DB limits
                if len(batch) >= 50:
                    await flush(batch)
                    batch.clear()

            await flush(batch)
                
        logger.info(f"LinkedIn complete: {total_stats}")
        return total_stats

    except Exception as exc:
        # C5 FIX: Previously there was no try/except here — any 403/429
        # or network error crashed silently with no retry. Now it retries
        # once (max_retries=1) with a 120s backoff before giving up.
        logger.error(f"LinkedIn scrape failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)

    finally:
        # C5 FIX: Unconditionally release the lock on exit (success OR
        # failure). Previously there was no finally block, so a failed
        # LinkedIn scrape left the lock set for 600s (10 min), blocking
        # all subsequent manual refreshes from the UI.
        if lock_acquired:
            await redis.delete(lock_key)


@celery_app.task(
    name="app.tasks.job_tasks.enrich_job_with_ai",
    bind=True,
    max_retries=2,
    queue="ai",
    # Must not exceed the Gemini quota. The free tier allows 5 requests/min
    # for gemini-3.8-flash; dispatching at 15/m guaranteed a constant stream
    # of 429s. Each job makes TWO calls (skills + embedding), so 2/m of
    # headroom keeps us inside the limit. Override via GEMINI_RATE_LIMIT.
    rate_limit=settings.GEMINI_RATE_LIMIT,
)
def enrich_job_with_ai(self, job_id: str):
    from asgiref.sync import async_to_sync
    return async_to_sync(_enrich_job_with_ai)(self, job_id, self.request.id)

async def _enrich_job_with_ai(self, job_id: str, task_id: str = None):
    """
    Celery task: enrich a single job with Gemini AI.
    
    Called after a job is saved to the database.
    Extracts skills, generates embedding, updates the record.
    """
    logger.info(f"[{task_id or self.request.id}] Enriching job {job_id}")
    
    try:
        async with create_worker_session_ctx() as session:
            job = await session.get(Job, uuid.UUID(job_id))
            if not job:
                logger.error(f"Job {job_id} not found")
                return

            if not job.description:
                logger.info(f"Job {job_id} has no description — skipping AI")
                job.scrape_status = "enriched"
                job.enriched_at = utc_now()
                session.add(job)
                await session.commit()
                # Publish even for jobs with no description — a small number
                # of postings are behind JS-only boards that jd_extractor
                # can't reach, and they should still appear on the live board.
                await _publish_job_event(job, skills=[])
                return

            # Extract skills using Gemini
            skills = await extract_skills(job.title, job.description)

            # Generate vector embedding
            text_for_embedding = f"{job.title} {job.company} {job.description}"
            embedding = await generate_embedding(text_for_embedding)

            # Update the job record
            job.skills = skills
            job.embedding = embedding
            job.scrape_status = "enriched"
            job.enriched_at = utc_now()   # existed on the model but was never set

            session.add(job)
            await session.commit()
            
            logger.info(f"Job {job_id} enriched: {len(skills)} skills, embedding={len(embedding)}d")
            
            # Publish to SSE channel for live board updates
            await _publish_job_event(job, skills=skills)

    except Exception as exc:
        logger.error(f"AI enrichment failed for job {job_id}: {exc}")

        # Dead Letter Queue: on the final attempt, park the job as failed so
        # it stops being re-selected by process_raw_jobs_batch.
        if self.request.retries >= self.max_retries:
            async with create_worker_session_ctx() as session:
                job = await session.get(Job, uuid.UUID(job_id))
                if job:
                    job.scrape_status = "failed"
                    session.add(job)
                    await session.commit()
            logger.warning(f"Job {job_id} marked as failed after max retries")
            # Re-raise the ORIGINAL error. Calling self.retry() here raised
            # MaxRetriesExceededError, which masked the real cause in Flower
            # and in the logs.
            raise

        # Honour the delay the provider asked for. A flat 30s retry against a
        # 5 req/min free-tier quota just re-saturates it, turning one 429 into
        # a self-sustaining retry storm.
        countdown = 30
        retry_after = getattr(exc, "retry_after", None)
        if retry_after:
            countdown = retry_after + random.randint(2, 10)  # jitter: don't sync workers
        raise self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    name="app.tasks.job_tasks.process_raw_jobs_batch",
    bind=True,
    max_retries=1,
    queue="ai",
)
def process_raw_jobs_batch(self, batch_size: int = 10):
    from asgiref.sync import async_to_sync
    return async_to_sync(_process_raw_jobs_batch)(self, batch_size, self.request.id)

async def _process_raw_jobs_batch(self, batch_size: int = 10, task_id: str = None):
    """
    Periodic task: claim 'raw' jobs and enqueue them for AI enrichment.

    Jobs are CLAIMED (status raw -> queued) in the same transaction that
    selects them, using FOR UPDATE SKIP LOCKED. Previously this selected
    `scrape_status == 'raw' LIMIT 10` and left the status untouched: since
    enrich_job_with_ai is async and rate-limited to 15/min, the same ten rows
    were still 'raw' when beat fired again 60s later, so they were re-enqueued
    every single minute until they happened to drain — duplicated Gemini spend
    and duplicated SSE publishes for every job.
    """
    logger.info(f"[{task_id or self.request.id}] Starting AI Enrichment Batch")

    try:
        async with create_worker_session_ctx() as session:
            # SKIP LOCKED lets concurrent beat ticks / multiple workers claim
            # disjoint rows instead of contending on the same ones.
            claimed = await session.execute(
                text(
                    """
                    UPDATE jobs SET scrape_status = 'queued'
                    WHERE id IN (
                        SELECT id FROM jobs
                        WHERE scrape_status = 'raw'
                        ORDER BY scraped_at
                        LIMIT :limit
                        FOR UPDATE SKIP LOCKED
                    )
                    RETURNING id
                    """
                ),
                {"limit": batch_size},
            )
            job_ids = [row[0] for row in claimed]
            await session.commit()

            if not job_ids:
                return "No raw jobs found"

            for job_id in job_ids:
                enrich_job_with_ai.delay(str(job_id))

            return f"Enqueued {len(job_ids)} jobs for enrichment"

    except Exception as exc:
        # Re-raise: swallowing this returned None and made failures invisible
        # to Celery, so a persistently broken batch looked like a success.
        logger.error(f"Batch failed: {exc}", exc_info=True)
        raise


@celery_app.task(
    name="app.tasks.job_tasks.requeue_stuck_jobs",
    bind=True,
    queue="ai",
)
def requeue_stuck_jobs(self, stale_after_minutes: int = 30):
    from asgiref.sync import async_to_sync
    return async_to_sync(_requeue_stuck_jobs)(self, stale_after_minutes)


async def _requeue_stuck_jobs(self, stale_after_minutes: int = 30):
    """
    Return jobs stranded in 'queued' back to 'raw'.

    Claiming rows means a worker that dies mid-enrichment leaves them
    'queued' forever. This reaper is the counterpart that makes the claim
    safe.
    """
    async with create_worker_session_ctx() as session:
        result = await session.execute(
            text(
                """
                UPDATE jobs SET scrape_status = 'raw'
                WHERE scrape_status = 'queued'
                  AND scraped_at < NOW() - (:mins || ' minutes')::interval
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
    name="app.tasks.job_tasks.backfill_descriptions",
    bind=True,
    queue="scraping",
)
def backfill_descriptions(self, batch_size: int = 50):
    from asgiref.sync import async_to_sync
    return async_to_sync(_backfill_descriptions)(self, batch_size)


async def _backfill_descriptions(self, batch_size: int = 50):
    """
    Populate `description` for jobs crawled before JD extraction existed.

    Targets rows that were never attempted (description_fetched_at IS NULL),
    so repeated runs walk forward through the backlog instead of retrying the
    same unreachable postings. A row whose fetch genuinely yields nothing gets
    description_fetched_at stamped anyway, marking it "attempted".

    Re-queues successfully backfilled rows for AI enrichment, since they were
    previously marked 'enriched' with zero skills purely because they had no
    description to work from.
    """
    async with create_worker_session_ctx() as session:
        rows = (await session.execute(
            select(Job)
            .where(Job.description.is_(None))
            .where(Job.description_fetched_at.is_(None))
            .where(Job.is_active == True)  # noqa: E712
            .order_by(Job.scraped_at.desc())
            .limit(batch_size)
        )).scalars().all()

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
        for job, record in zip(rows, records):
            job.description_fetched_at = now
            if record.get("description"):
                job.description = record["description"]
                # Force re-enrichment now that there is text to analyse.
                job.scrape_status = "raw"
                requeued += 1
            session.add(job)
        await session.commit()

    logger.info("Backfill: %d/%d rows gained a description", filled, len(rows))
    return f"Backfilled {filled}/{len(rows)}, requeued {requeued} for enrichment"
