import asyncio
from app.workers.celery_app import celery_app
from app.services.scrapers.simplify import SimplifyScraper
from app.services.scrapers.linkedin import LinkedInScraper
from app.services.scrapers.utils import DedupService
from app.services.scrapers.job_sync_service import JobSyncService

@celery_app.task(bind=True, name="tasks.sync_simplify_jobs", max_retries=3, default_retry_delay=60)
def sync_simplify_jobs(self, user_id: str):
    """
    Synchronizes jobs from the Simplify markdown tracker.
    """
    try:
        self.update_state(state='PROGRESS', meta={'message': 'Initializing Simplify scraper...'})
        dedup = DedupService()
        scraper = SimplifyScraper()
        sync_service = JobSyncService()
        
        self.update_state(state='PROGRESS', meta={'message': 'Fetching jobs from Simplify...'})
        raw_jobs = asyncio.run(scraper.fetch_and_parse())
        
        self.update_state(state='PROGRESS', meta={'message': f'Processing {len(raw_jobs)} jobs...'})
        # Filter out recently seen URLs (L1 cache within DedupService)
        jobs = [j for j in raw_jobs if not dedup.is_recently_seen(j["job_url"], user_id)]
        
        self.update_state(state='PROGRESS', meta={'message': f'Syncing {len(jobs)} new jobs to database...'})
        sync_service.sync_jobs_sync(jobs, user_id)
        
        # Mark as seen
        for job in jobs:
            dedup.mark_as_seen(job["job_url"], user_id)
            
        return f"Successfully processed {len(jobs)} new jobs from Simplify ({len(raw_jobs)} found)."
    except Exception as exc:
        raise self.retry(exc=exc)

@celery_app.task(bind=True, name="tasks.sync_linkedin_jobs", max_retries=3, default_retry_delay=60)
def sync_linkedin_jobs(self, user_id: str, search_url: str):
    """
    Synchronizes jobs from LinkedIn using Playwright.
    """
    try:
        self.update_state(state='PROGRESS', meta={'message': 'Initializing LinkedIn scraper...'})
        dedup = DedupService()
        scraper = LinkedInScraper()
        sync_service = JobSyncService()
        
        self.update_state(state='PROGRESS', meta={'message': 'Fetching jobs from LinkedIn (this may take a few minutes)...'})
        raw_jobs = asyncio.run(scraper.fetch_and_parse(search_url))
        
        self.update_state(state='PROGRESS', meta={'message': f'Processing {len(raw_jobs)} jobs...'})
        # Filter out recently seen URLs
        jobs = [j for j in raw_jobs if not dedup.is_recently_seen(j["job_url"], user_id)]
        
        self.update_state(state='PROGRESS', meta={'message': f'Syncing {len(jobs)} new jobs to database...'})
        sync_service.sync_jobs_sync(jobs, user_id)
        
        # Mark as seen
        for job in jobs:
            dedup.mark_as_seen(job["job_url"], user_id)
            
        return f"Successfully processed {len(jobs)} new jobs from LinkedIn ({len(raw_jobs)} found)."
    except Exception as exc:
        raise self.retry(exc=exc)
