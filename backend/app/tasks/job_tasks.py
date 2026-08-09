import logging
from datetime import datetime
import json
import uuid
import os

from sqlmodel import select
from sqlalchemy import update

from app.tasks.celery_app import celery_app
from app.scraping.parsers.github import parse_github_jobs
from app.scraping.db_sync import DatabaseSyncService
from app.core.database import create_worker_session
from app.models.job import Job
from app.ai.skill_extractor import extract_skills
from app.ai.embedder import generate_embedding
from app.core.redis import create_worker_redis
from app.schemas.job import JobCreate
from app.scraping.parsers.linkedin import LinkedInScraper

logger = logging.getLogger(__name__)

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
    scrape_start_time = datetime.utcnow()

    # Acquire the lock inside the async body so it applies to
    # BOTH API-triggered and Beat-triggered runs.
    lock_acquired = await redis.set(lock_key, "locked", nx=True, ex=600)
    if not lock_acquired:
        logger.info(f"[{task_id}] GitHub scrape already running — skipping (lock held)")
        return {"status": "skipped", "reason": "lock_held"}
    
    try:
        total_stats = {"new": 0, "skipped": 0, "updated": 0, "source": "github"}
        
        WorkerSession = create_worker_session()
        async with WorkerSession() as session:
            db_service = DatabaseSyncService(session)
            batch = []
            
            job_gen, successful_urls = await parse_github_jobs()
            seen_external_ids = []
            for job in job_gen:
                batch.append(job.model_dump())
                seen_external_ids.append(job.external_id)
                
                if len(batch) >= 100:
                    upserted_count = await db_service.bulk_upsert_jobs(batch)
                    total_stats["new"] += upserted_count
                    batch.clear()
            
            if batch:
                upserted_count = await db_service.bulk_upsert_jobs(batch)
                total_stats["new"] += upserted_count
            
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

        total_stats = {"new": 0, "updated": 0, "source": "linkedin"}
        
        WorkerSession = create_worker_session()
        async with WorkerSession() as session:
            db_service = DatabaseSyncService(session)
            batch = []

            for job_dict in raw_jobs:
                job = JobCreate(**job_dict)
                batch.append(job.model_dump())
                
                # Sync in chunks of 50 to respect memory and DB limits
                if len(batch) >= 50:
                    upserted_count = await db_service.bulk_upsert_jobs(batch)
                    total_stats["new"] += upserted_count
                    batch.clear()
            
            # Flush remaining
            if batch:
                upserted_count = await db_service.bulk_upsert_jobs(batch)
                total_stats["new"] += upserted_count
                
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
    rate_limit="15/m",
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
    
    WorkerSession = create_worker_session()
    try:
        async with WorkerSession() as session:
            job = await session.get(Job, uuid.UUID(job_id))
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            if not job.description:
                logger.info(f"Job {job_id} has no description — skipping AI")
                job.scrape_status = "enriched"
                session.add(job)
                await session.commit()
                # Publish even for jobs with no description — GitHub jobs from
                # README tables never have descriptions but should still appear
                # on the live board immediately after enrichment completes.
                redis = create_worker_redis()
                await redis.publish(
                    "new_jobs_channel",
                    json.dumps({
                        "id": str(job.id),
                        "title": job.title,
                        "company": job.company,
                        "location": job.location,
                        "skills": [],
                        "apply_url": job.apply_url,
                        "source": job.source,
                        "is_remote": job.is_remote,
                    })
                )
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
            
            session.add(job)
            await session.commit()
            
            logger.info(f"Job {job_id} enriched: {len(skills)} skills, embedding={len(embedding)}d")
            
            # Publish to SSE channel for live board updates
            redis = create_worker_redis()
            await redis.publish(
                "new_jobs_channel",
                json.dumps({
                    "id": str(job.id),
                    "title": job.title,
                    "company": job.company,
                    "location": job.location,
                    "skills": skills,
                    "apply_url": job.apply_url,
                    "source": job.source,
                    "is_remote": job.is_remote,
                })
            )
            
    except Exception as exc:
        logger.error(f"AI enrichment failed for job {job_id}: {exc}")
        
        # Dead Letter Queue implementation
        # If this is the last retry, mark as failed
        if self.request.retries >= self.max_retries:
            async with WorkerSession() as session:
                job = await session.get(Job, uuid.UUID(job_id))
                if job:
                    job.scrape_status = "failed"
                    session.add(job)
                    await session.commit()
            logger.warning(f"Job {job_id} marked as failed after max retries")
            
        raise self.retry(exc=exc, countdown=30)


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
    Periodic task: Find 'raw' jobs and enqueue them for enrichment.
    Rate limiting is handled by Celery on the enrich_job_with_ai task itself.
    """
    logger.info(f"[{task_id or self.request.id}] Starting AI Enrichment Batch")

    try:
        WorkerSession = create_worker_session()
        async with WorkerSession() as session:
            query = select(Job).where(Job.scrape_status == "raw").limit(batch_size)
            result = await session.execute(query)
            jobs = result.scalars().all()

            if not jobs:
                return "No raw jobs found"

            enqueued = 0
            for job in jobs:
                # Dispatch individual tasks. Celery naturally throttles based on rate_limit
                enrich_job_with_ai.delay(str(job.id))
                enqueued += 1

            return f"Enqueued {enqueued} jobs for enrichment"

    except Exception as exc:
        logger.error(f"Batch failed: {exc}", exc_info=True)