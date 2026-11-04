import logging
import random
import re
from datetime import datetime, timedelta
import uuid
import os
from typing import Optional

from sqlmodel import select
from sqlalchemy import String, all_, bindparam, func, text, update
from sqlalchemy.dialects.postgresql import ARRAY

from app.tasks.celery_app import celery_app
from app.tasks.runtime import HARD_LIMIT_GRACE, run_async
from app.scraping.parsers.github import parse_github_jobs
from app.scraping.db_sync import DatabaseSyncService
from app.scraping.jd_extractor import enrich_with_descriptions
from app.core.database import create_worker_session_ctx
from app.core.datetime_utils import as_utc, utc_now
from app.core.locks import acquire_lock, release_lock
from app.models.job import Job
from app.ai.gemini_client import (
    GeminiConfigError,
    GeminiThrottled,
    GeminiTransientError,
    GeminiTruncatedError,
    acquire_gemini_slots,
)
from app.ai.skill_extractor import extract_job_attributes
from app.ai.embedder import generate_embedding
from app.core.redis import create_worker_redis
from app.core.events import KIND_ENRICHED, job_event_payload, publish_job_event
from app.config import settings
from app.schemas.job import JobCreate
from app.scraping.parsers.linkedin import LinkedInScraper

logger = logging.getLogger(__name__)

# A first crawl against an empty DB fetches a JD for every posting (~1s each
# at concurrency 4), so a crawl gets most of an hour. The lock must outlive
# the hard limit, or a crawl killed at the limit could still be running when
# the next one takes the lock.
SCRAPE_TIMEOUT = 3300
SCRAPE_LOCK_TTL_SECONDS = 3600
BACKFILL_TIMEOUT = 1500

# Each enriched job costs two Gemini calls: attribute extraction + embedding.
CALLS_PER_ENRICHMENT = 2
# process_raw_jobs_batch keeps at most this many minutes of enrichment work
# queued in the broker (at GEMINI_RATE_LIMIT). It used to claim 10 jobs a
# minute against a 2/min drain, so the backlog grew until the reaper's
# deadline put still-queued jobs back to 'raw' and they were enqueued twice.
QUEUE_DEPTH_MINUTES = 2
# Well past the longest a job can sit queued under the cap above, plus its
# retries; only jobs whose worker died should still be 'queued' this long.
STUCK_AFTER_MINUTES = 60
# LinkedIn postings are never removed from a README the way GitHub's are, so
# without this they stayed in the feed forever. A posting is retired once
# the daily crawl hasn't seen it for this long.
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
    # Redis Stream, not pub/sub: pub/sub had no backlog, so any event
    # published while a client was reconnecting was lost forever.
    await publish_job_event(redis, job_event_payload(job, KIND_ENRICHED, skills))


async def deactivate_unseen_github(
    db_service: DatabaseSyncService, source_urls: list, seen_external_ids: list
) -> int:
    """
    Deactivate GitHub postings from successfully crawled READMEs that this
    crawl no longer lists, then relink their hashes. Does not commit.
    """
    stmt = (
        update(Job)
        .where(Job.source == "github")
        .where(Job.source_url.in_(source_urls))
        # One array parameter. notin_() sent one bind parameter per id, and
        # asyncpg refuses statements with more than 32,767 of them.
        .where(Job.external_id != all_(
            bindparam("seen_ids", seen_external_ids, type_=ARRAY(String))
        ))
        .where(Job.is_active == True)  # noqa: E712
        .values(is_active=False)
        .returning(Job.canonical_hash)
    )
    deactivated = (await db_service.session.execute(stmt)).scalars().all()
    # A deactivated canonical row must hand canonical status to an active
    # duplicate, or that duplicate disappears from the feed.
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
    """
    Celery task: scrape internship listings from GitHub repos
    """
    logger.info(f"[{task_id or self.request.id}] Starting Github scrape")

    redis = create_worker_redis()
    lock_key = "scrape_lock:github"

    # Acquire the lock inside the async body so it applies to
    # BOTH API-triggered and Beat-triggered runs.
    lock_token = await acquire_lock(redis, lock_key, SCRAPE_LOCK_TTL_SECONDS)
    if not lock_token:
        logger.info(f"[{task_id}] GitHub scrape already running — skipping (lock held)")
        await redis.aclose()
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
                # GitHub READMEs are just link tables, so the JD lives behind
                # apply_url on the ATS. sync_batch dedups FIRST and only
                # fetches descriptions for postings that still need one.
                result = await db_service.sync_batch(records, enrich_with_descriptions)
                for key in total_stats:
                    if key in result:
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
                total_stats["deactivated"] = await deactivate_unseen_github(
                    db_service, successful_urls, seen_external_ids
                )
            await session.commit()

        logger.info(f"GitHub complete: {total_stats}")
        return total_stats
    except Exception as exc:
        logger.error(f"GitHub scrape failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))
    finally:
        # Releases only OUR lock: if this run outlived the TTL and another
        # run now holds the key, its lock is left alone.
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose()


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
    """
    Celery task: sequentially scrape LinkedIn job pages
    """
    logger.info(f"[{task_id or self.request.id}] Starting LinkedIn scrape for {search_url}")
    redis = create_worker_redis()
    lock_key = "scrape_lock:linkedin"

    # Acquire the lock inside the async body so Beat-triggered runs are also
    # protected. If another run holds it, skip rather than run a duplicate.
    lock_token = await acquire_lock(redis, lock_key, SCRAPE_LOCK_TTL_SECONDS)
    if not lock_token:
        logger.info(f"[{task_id}] LinkedIn scrape already running — skipping (lock held)")
        await redis.aclose()
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
                # One extra request per NEW job against LinkedIn's guest
                # detail endpoint; already-synced postings cost nothing.
                result = await db_service.sync_batch(records, enrich_with_descriptions)
                for key in total_stats:
                    if key in result:
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
        # Retries once (max_retries=1) with a 120s backoff before giving up.
        logger.error(f"LinkedIn scrape failed: {exc}", exc_info=True)
        raise self.retry(exc=exc, countdown=120)

    finally:
        # Released on every exit, success or failure, but only if still ours.
        await release_lock(redis, lock_key, lock_token)
        await redis.aclose()


# ── AI enrichment ────────────────────────────────────────────────────────
#
# A job is enriched under a CLAIM: process_raw_jobs_batch sets
# scrape_status='queued' and stamps queued_at, and passes that timestamp to
# the task. The task proceeds, and writes its result, only while the row is
# still queued under that same timestamp. If the reaper hands the row back
# and it is claimed again, or a new description resets it to 'raw', the
# older task finds its claim gone and does nothing — so a job is enriched
# (and announced over SSE) once, not once per enqueued message.

def _claimed(stmt, job_id: uuid.UUID, claimed_at: Optional[datetime]):
    stmt = stmt.where(Job.id == job_id, Job.scrape_status == "queued")
    if claimed_at is not None:
        stmt = stmt.where(Job.queued_at == claimed_at)
    return stmt


def _holds_claim(job: Job, claimed_at: Optional[datetime]) -> bool:
    if job.scrape_status != "queued":
        return False
    # Messages enqueued before claims carried a timestamp have none.
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
    # A per-worker cap on top of the shared GEMINI_REQUESTS_PER_MINUTE
    # budget enforced by acquire_gemini_slots.
    rate_limit=settings.GEMINI_RATE_LIMIT,
)
def enrich_job_with_ai(self, job_id: str, claim: Optional[str] = None):
    return run_async(_enrich_job_with_ai, self, job_id, claim, self.request.id)

async def _enrich_job_with_ai(self, job_id: str, claim: Optional[str] = None, task_id: str = None):
    """
    Celery task: enrich a single job with Gemini AI.

    Extracts skills, pay and level, generates the embedding, and writes them
    back — all under the claim described above.
    """
    logger.info(f"[{task_id or self.request.id}] Enriching job {job_id}")
    jid = uuid.UUID(job_id)
    claimed_at = datetime.fromisoformat(claim) if claim else None
    redis = create_worker_redis()

    try:
        async with create_worker_session_ctx() as session:
            job = await session.get(Job, jid)
            if not job:
                logger.error(f"Job {job_id} not found")
                return "missing"
            if not _holds_claim(job, claimed_at):
                logger.info(f"Job {job_id} is no longer claimed by this task — skipping")
                return "skipped"

            values = {"scrape_status": "enriched", "enriched_at": utc_now(), "queued_at": None}
            skills: list = []

            # Jobs with no description (JS-only boards jd_extractor can't
            # reach) skip Gemini but are still marked done and announced.
            if job.description:
                # Reserve both calls up front, so a job never gets its
                # attributes and then stalls on the embedding.
                await acquire_gemini_slots(redis, CALLS_PER_ENRICHMENT)

                # One structured call: skills plus pay / seniority / employment.
                attrs = await extract_job_attributes(job.title, job.description)
                skills = attrs.skills
                embedding = await generate_embedding(f"{job.title} {job.company} {job.description}")

                values.update(skills=skills, embedding=embedding)
                # Pay and level only fill gaps: a value that came from the
                # source posting wins over the model's reading.
                if job.salary_min is None and job.salary_max is None and attrs.salary_period:
                    values.update(
                        salary_min=attrs.salary_min,
                        salary_max=attrs.salary_max,
                        salary_period=attrs.salary_period,
                    )
                if not job.seniority_level and attrs.seniority_level:
                    values["seniority_level"] = attrs.seniority_level
                if not job.employment_type and attrs.employment_type:
                    values["employment_type"] = attrs.employment_type

            # Conditional write: lands only if the claim survived the Gemini
            # round trip.
            written = (await session.execute(
                _claimed(update(Job), jid, claimed_at)
                .values(**values)
                .returning(Job.is_active, Job.canonical_id)
            )).first()
            await session.commit()

        if written is None:
            logger.info(f"Job {job_id} was re-claimed while enriching — result discarded")
            return "superseded"

        logger.info(f"Job {job_id} enriched: {len(skills)} skills")
        # Only feed-visible rows are announced, matching db_sync's `created`
        # events; duplicates and closed postings used to trigger skill alerts.
        is_active, canonical_id = written
        if is_active and canonical_id is None:
            await _publish_job_event(redis, job, skills)
        return "enriched"

    except GeminiThrottled as exc:
        # The shared budget is spent and no call was made. Hand the job back
        # for the next batch instead of burning one of its retries.
        await _end_claim(jid, claimed_at, "raw")
        logger.info(f"Job {job_id} deferred: {exc}")
        return "throttled"

    except GeminiConfigError:
        # A deployment fault (bad key, retired model), not this job's fault:
        # fail loudly on the first attempt, and leave the job to be picked
        # up again once the configuration is fixed.
        await _end_claim(jid, claimed_at, "raw")
        raise

    except GeminiTruncatedError:
        # Retrying the same input hits the same ceiling.
        await _end_claim(jid, claimed_at, "failed")
        raise

    except GeminiTransientError as exc:
        if self.request.retries >= self.max_retries:
            # Out of retries on an upstream blip: requeue rather than park
            # the job as failed for good.
            await _end_claim(jid, claimed_at, "raw")
            raise
        # Honour the delay the provider asked for. A flat 30s retry against a
        # 5 req/min free-tier quota just re-saturates it.
        countdown = (exc.retry_after or 30) + random.randint(2, 10)  # jitter: don't sync workers
        raise self.retry(exc=exc, countdown=countdown)

    except Exception as exc:
        logger.error(f"AI enrichment failed for job {job_id}: {exc}")
        if self.request.retries >= self.max_retries:
            # Dead letter: park as failed so it stops being re-selected.
            await _end_claim(jid, claimed_at, "failed")
            logger.warning(f"Job {job_id} marked as failed after max retries")
            # Re-raise the ORIGINAL error. Calling self.retry() here raised
            # MaxRetriesExceededError, which masked the real cause.
            raise
        raise self.retry(exc=exc, countdown=30)

    finally:
        await redis.aclose()


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
    Periodic task: claim 'raw' jobs and enqueue them for AI enrichment.

    Jobs are CLAIMED (status raw -> queued) in the same statement that
    selects them, using FOR UPDATE SKIP LOCKED, and each message carries its
    claim timestamp. The number claimed tops the queue up to
    QUEUE_DEPTH_MINUTES of work at GEMINI_RATE_LIMIT, never more.
    """
    logger.info(f"[{task_id or self.request.id}] Starting AI Enrichment Batch")

    capacity = max(1, round(_tasks_per_minute(settings.GEMINI_RATE_LIMIT) * QUEUE_DEPTH_MINUTES))

    try:
        async with create_worker_session_ctx() as session:
            queued = (await session.execute(
                select(func.count()).select_from(Job).where(Job.scrape_status == "queued")
            )).scalar_one()
            limit = min(batch_size, capacity - queued)
            if limit <= 0:
                return f"Queue full ({queued} queued)"

            # SKIP LOCKED lets concurrent beat ticks / multiple workers claim
            # disjoint rows instead of contending on the same ones.
            claimed = (await session.execute(
                text(
                    """
                    UPDATE jobs SET scrape_status = 'queued', queued_at = NOW()
                    WHERE id IN (
                        SELECT id FROM jobs
                        WHERE scrape_status = 'raw'
                        ORDER BY scraped_at
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
                enrich_job_with_ai.delay(str(job_id), as_utc(queued_at).isoformat())

            return f"Enqueued {len(claimed)} jobs for enrichment"

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
def requeue_stuck_jobs(self, stale_after_minutes: int = STUCK_AFTER_MINUTES):
    return run_async(_requeue_stuck_jobs, self, stale_after_minutes)


async def _requeue_stuck_jobs(self, stale_after_minutes: int = STUCK_AFTER_MINUTES):
    """
    Return jobs stranded in 'queued' back to 'raw'.

    Claiming rows means a worker that dies mid-enrichment leaves them
    'queued' forever. This reaper is the counterpart that makes the claim
    safe; clearing queued_at also voids the dead task's claim, so a message
    for it that is redelivered later does nothing.
    """
    async with create_worker_session_ctx() as session:
        result = await session.execute(
            text(
                """
                UPDATE jobs SET scrape_status = 'raw', queued_at = NULL
                WHERE scrape_status = 'queued'
                  -- queued_at, not scraped_at: an old posting claimed a
                  -- second ago has an old scraped_at and was requeued while
                  -- still being enriched.
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
    """
    Retire postings a crawl hasn't seen for `max_age_days`.

    scraped_at is refreshed every time a crawl sees a posting (db_sync
    _touch / upsert), so it is the "last seen" time.
    """
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
        # As with the GitHub deactivation: an active duplicate must take
        # over canonical status, or it vanishes from the feed too.
        await DatabaseSyncService(session).relink_hashes({h for h in deactivated if h})
        await session.commit()
    if deactivated:
        logger.info("Deactivated %d %s postings unseen for %d days", len(deactivated), source, max_age_days)
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
            select(Job.id, Job.external_id, Job.source, Job.apply_url)
            .where(Job.description.is_(None))
            .where(Job.description_fetched_at.is_(None))
            .where(Job.is_active == True)  # noqa: E712
            .order_by(Job.scraped_at.desc())
            .limit(batch_size)
        )).all()
        # End the read transaction before the network fetch; holding it open
        # left Postgres "idle in transaction" for the whole fetch.
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
        for row, record in zip(rows, records):
            values = {"description_fetched_at": now}
            if record.get("description"):
                # Force re-enrichment now that there is text to analyse.
                # Resetting to 'raw' even from 'queued' voids an in-flight
                # claim that would otherwise mark the job enriched without
                # ever reading this description.
                values.update(
                    description=record["description"],
                    description_source=record.get("description_source"),
                    scrape_status="raw",
                    queued_at=None,
                )
            # Guarded on description IS NULL: a crawl may have filled it
            # while we were fetching.
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
