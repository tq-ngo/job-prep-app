import logging
from typing import List, Dict, Any
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.job import Job

logger = logging.getLogger(__name__)

class DatabaseSyncService:
    """
    Handles bulk asynchronous PostgreSQL UPSERT operations
    to maximize sync throughput and prevent connection pool exhaustion.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert_jobs(self, job_records: List[Dict[str, Any]]) -> int:
        """
        Executes a high-throughput ON CONFLICT DO UPDATE query for a batch of jobs.
        
        Uses the (external_id, source) unique constraint defined on the Job model
        to detect duplicates. On conflict, updates mutable fields.
        """
        if not job_records:
            return 0

        # Construct PostgreSQL INSERT statement
        stmt = insert(Job).values(job_records)

        # Define update map for existing records matching the unique constraint
        update_cols = {
            "title": stmt.excluded.title,
            "company": stmt.excluded.company,
            "location": stmt.excluded.location,
            "salary_min": stmt.excluded.salary_min,
            "salary_max": stmt.excluded.salary_max,
            "apply_url": stmt.excluded.apply_url,
            "description": stmt.excluded.description,
            "is_remote": stmt.excluded.is_remote,
            "posted_at": stmt.excluded.posted_at,
            "scraped_at": stmt.excluded.scraped_at,
            "is_active": stmt.excluded.is_active,
        }

        # PostgreSQL ON CONFLICT using the (external_id, source) unique constraint
        upsert_stmt = stmt.on_conflict_do_update(
            constraint="uq_jobs_external_id_source",
            set_=update_cols
        )

        try:
            result = await self.session.execute(upsert_stmt)
            await self.session.commit()
            logger.info(f"Successfully bulk-upserted {len(job_records)} job records.")
            return result.rowcount
        except Exception as exc:
            await self.session.rollback()
            logger.error(f"Failed executing bulk upsert to database: {exc}")
            raise exc