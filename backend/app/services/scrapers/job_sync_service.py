from typing import List, Dict
from uuid import UUID
from sqlmodel import select
from app.core.database import async_session_maker
from app.models.jobs import JobApplication


class JobSyncService:
    """
    Handles all DB persistence for scraped jobs.
    Completely decoupled from scraping logic — accepts plain dicts.
    """

    async def sync_jobs(self, jobs: List[Dict[str, str]], user_id: UUID) -> int:
        """
        Persist new jobs to the database, skipping any duplicates by URL.
        Returns the count of newly inserted records.

        Uses a bulk URL pre-fetch to avoid N+1 queries inside the loop.
        """
        if not jobs:
            return 0

        async with async_session_maker() as session:
            # Bulk fetch all existing URLs in one query instead of N individual SELECTs
            existing_urls = await self._get_existing_urls(session)

            new_jobs = [
                JobApplication(
                    company_name=job.get("company_name", ""),
                    job_title=job.get("job_title", ""),
                    job_url=job["job_url"],
                    location=job.get("location", ""),
                    source=job.get("source", "Unknown"),
                    user_id=user_id,
                )
                for job in jobs
                if job.get("url") and job["url"] not in existing_urls
            ]

            if new_jobs:
                session.add_all(new_jobs)
                await session.commit()

        return len(new_jobs)

    async def _get_existing_urls(self, session) -> set:
        """Fetch all tracked job URLs into a set for O(1) duplicate checks."""
        result = await session.execute(select(JobApplication.job_url))
        return set(result.scalars().all())