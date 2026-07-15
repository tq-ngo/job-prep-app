import logging
from datetime import datetime
import json
import uuid

from sqlmodel import select
from sqlalchemy import update

from app.tasks.celery_app import celery_app
from app.scraping.parsers.github import parse_github_jobs
from app.scraping.db_sync import sync_jobs_batch
from app.core.database import AsyncSessionLocal
from app.models.job import Job
from app.ai.skill_extractor import extract_skills
from app.ai.embedder import generate_embedding
from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)

@celery_app.task(
    name="app.tasks.job_tasks.scrape_github",
    bind=True,
    max_retries=3,
    queue="scraping",
)
def scrape_github(self):
    from asgiref.sync import async_to_sync
    return async_to_sync(_scrape_github)(self)

async def _scrape_github(self):
    """
    Celery task: scrape internship listings from GitHub repos
    """
    logger.info(f"[{self.request.id}] Starting Github scrape")
    
    redis = await get_redis_pool()
    lock_key = "scrape_lock:github"
    scrape_start_time = datetime.utcnow()
    
    try:
        total_stats = {"new": 0, "skipped": 0, "updated": 0, "source": "github"}
        
        async with AsyncSessionLocal() as session:
            batch = []
            
            job_gen, successful_urls = await parse_github_jobs()
            for job in job_gen:
                job.scraped_at = datetime.utcnow()
                batch.append(job)
                
                if len(batch) >= 100:
                    stats = await sync_jobs_batch(batch, session)
                    total_stats["new"] += stats.get("new", 0)
                    total_stats["updated"] += stats.get("updated", 0)
                    batch.clear()
            
            if batch:
                stats = await sync_jobs_batch(batch, session)
                total_stats["new"] += stats.get("new", 0)
                total_stats["updated"] += stats.get("updated", 0)
            
            if successful_urls:
                stmt = (
                    update(Job)
                    .where(Job.source == "github")
                    .where(Job.source_url.in_(successful_urls))
                    .where(Job.scraped_at < scrape_start_time)
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
    return async_to_sync(_enrich_job_with_ai)(self, job_id)

async def _enrich_job_with_ai(self, job_id: str):
    """
    Celery task: enrich a single job with Gemini AI.
    
    Called after a job is saved to the database.
    Extracts skills, generates embedding, updates the record.
    """
    logger.info(f"[{self.request.id}] Enriching job {job_id}")
    
    try:
        async with AsyncSessionLocal() as session:
            job = await session.get(Job, uuid.UUID(job_id))
            if not job:
                logger.error(f"Job {job_id} not found")
                return
            
            if not job.description:
                logger.info(f"Job {job_id} has no description — skipping AI")
                job.scrape_status = "enriched"
                session.add(job)
                await session.commit()
                return
            
            # Extract skills using Gemini
            skills = await extract_skills(job.title, job.description)
            
            # Generate vector embedding
            text_for_embedding = f"{job.title} {job.company} {job.description}"
            embedding = await generate_embedding(text_for_embedding)
            
            # Update the job record
            job.skills = skills
            job.embedding = embedding
            job.enriched_at = datetime.utcnow()
            job.scrape_status = "enriched"
            
            session.add(job)
            await session.commit()
            
            logger.info(f"Job {job_id} enriched: {len(skills)} skills, embedding={len(embedding)}d")
            
            # Publish to Redis Pub/Sub for WebSockets
            redis = await get_redis_pool()
            await redis.publish(
                "new_jobs_channel",
                json.dumps({
                    "id": str(job.id),
                    "title": job.title,
                    "company": job.company,
                    "skills": skills,
                    "apply_url": job.apply_url
                })
            )
            
    except Exception as exc:
        logger.error(f"AI enrichment failed for job {job_id}: {exc}")
        
        # Dead Letter Queue implementation
        # If this is the last retry, mark as failed
        if self.request.retries >= self.max_retries:
            async with AsyncSessionLocal() as session:
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
    return async_to_sync(_process_raw_jobs_batch)(self, batch_size)

async def _process_raw_jobs_batch(self, batch_size: int = 10):
    """
    Periodic task: Find 'raw' jobs and enqueue them for enrichment.
    Rate limiting is handled by Celery on the enrich_job_with_ai task itself.
    """
    logger.info(f"[{self.request.id}] Starting AI Enrichment Batch")

    try:
        async with AsyncSessionLocal() as session:
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