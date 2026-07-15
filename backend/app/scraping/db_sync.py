import logging
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlmodel import select

from app.models.job import Job
from app.schemas.job import JobCreate
from app.scraping.dedup import dedup_engine, url_to_sha256

logger = logging.getLogger(__name__)


async def sync_jobs_batch(
    jobs: List[JobCreate],
    session: AsyncSession,
    batch_size: int = 100,
) -> dict:
    
    stats = {"new": 0, "updated": 0}

    if not jobs:
        return stats
    
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        records = [
            {
                "external_id": j.external_id,
                "source": j.source,
                "source_url": getattr(j, "source_url", None),
                "title": j.title,
                "company": j.company,
                "location": j.location,
                "apply_url": j.apply_url,
                "description": j.description,
                "salary_min": j.salary_min,
                "salary_max": j.salary_max,
                "salary_currency": j.salary_currency,
                "is_remote": j.is_remote,
                "posted_at": j.posted_at.replace(tzinfo=None) if j.posted_at else None,
                "terms": j.terms,
                "scrape_status": "raw",
                "scraped_at": getattr(j, "scraped_at", None),
            }
            for j in batch
        ]
        
        stmt = pg_insert(Job).values(records)
        
        update_dict = {
            "title": stmt.excluded.title,
            "description": stmt.excluded.description,
            "is_active": True,
            "scraped_at": stmt.excluded.scraped_at
        }
        
        stmt = stmt.on_conflict_do_update(
            index_elements=["external_id", "source"],
            set_=update_dict
        )
        
        await session.execute(stmt)
        stats["new"] += len(batch) 
        
        await session.commit()
    
    return stats