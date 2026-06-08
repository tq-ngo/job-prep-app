import asyncio
import uuid
from app.workers.celery_app import celery_app
from app.services.scrapers.simplify import SimplifyScraper
from app.core.database import sync_engine
from sqlmodel import Session
from app.models.jobs import JobApplication

@celery_app.task(name="tasks.sync_simplify_jobs")
def sync_simplify_jobs(user_id: str):
    """
    Synchronizes jobs from the Simplify markdown tracker.
    Celery executes inside a synchronous thread execution framework,
    so we bridge the async event loop internally.
    """
    scraper = SimplifyScraper()
    jobs = asyncio.run(scraper.fetch_and_parse())
    
    # Persistent Sync Block to SQL Engine layer
    with Session(sync_engine) as session:
        for job in jobs:
            # Avoid inserting duplicate application profiles per user
            exists = session.query(JobApplication).filter(
                JobApplication.job_url == job["job_url"],
                JobApplication.user_id == uuid.UUID(user_id)
            ).first()
            
            if not exists:
                new_app = JobApplication(
                    company_name=job["company_name"],
                    job_title=job["job_title"],
                    job_url=job["job_url"],
                    location=job.get("location"),
                    source=job["source"],
                    user_id=uuid.UUID(user_id)
                )
                session.add(new_app)
        session.commit()
    return f"Successfully processed {len(jobs)} jobs."