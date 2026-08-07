import logging
from typing import List, Dict, Any
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from cachetools import LRUCache

from app.models.job import Job
from app.core.redis import create_worker_redis

logger = logging.getLogger(__name__)

# Layer 1: Module-level LRU cache. Stores up to 100k deduplication keys in memory per worker.
_seen_jobs_cache = LRUCache(maxsize=100_000)

class DatabaseSyncService:
    """
    Handles bulk asynchronous PostgreSQL UPSERT operations
    to maximize sync throughput and prevent connection pool exhaustion.
    """
    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert_jobs(self, job_records: List[Dict[str, Any]]) -> int:
        """
        Executes a high-throughput ON CONFLICT DO UPDATE query for a batch of jobs
        using a 3-layer deduplication pipeline.
        """
        if not job_records:
            return 0

        redis = create_worker_redis()
        
        # LAYER 1 & 2: Filter out jobs that are in LRU Cache or Redis
        filtered_records = []
        for r in job_records:
            ext_id = str(r.get("external_id"))
            source = str(r.get("source"))
            dedup_key = f"{source}:{ext_id}"
            
            # Layer 1: In-Memory LRU Cache check (O(1) local)
            if dedup_key in _seen_jobs_cache:
                continue
                
            # Layer 2: Redis Set check (O(1) network)
            is_seen = await redis.sismember("global_seen_jobs", dedup_key)
            if is_seen:
                # Hydrate the local cache so the next identical job short-circuits at Layer 1
                _seen_jobs_cache[dedup_key] = True
                continue
                
            filtered_records.append(r)
            
        if not filtered_records:
            logger.info("All jobs in batch are duplicates (caught by Cache/Redis).")
            return 0

        # Intra-batch deduplication to prevent CardinalityViolationError in Postgres
        deduped = {}
        for r in filtered_records:
            key = (r.get("external_id"), r.get("source"))
            deduped[key] = r
        job_records = list(deduped.values())

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
            
            # Post-DB insert: Add new/updated signatures to Redis and LRU cache
            for r in job_records:
                ext_id = str(r.get("external_id"))
                source = str(r.get("source"))
                dedup_key = f"{source}:{ext_id}"
                
                await redis.sadd("global_seen_jobs", dedup_key)
                _seen_jobs_cache[dedup_key] = True
                
            logger.info(f"Successfully bulk-upserted {len(job_records)} job records.")
            return result.rowcount
        except Exception as exc:
            await self.session.rollback()
            logger.error(f"Failed executing bulk upsert to database: {exc}")
            raise exc