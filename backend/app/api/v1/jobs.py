from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.models.jobs import JobApplication
from app.workers.tasks import sync_simplify_jobs
from typing import List

router = APIRouter()

@router.get("/", response_model=List[JobApplication])
async def read_jobs(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session)
):
    stmt = select(JobApplication).offset(skip).limit(limit)
    result = await session.execute(stmt)
    return result.scalars().all()

@router.post("/trigger-sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scraping_pipeline():
    """
    Enqueues a background scrape job via Celery.
    Returns immediately with a task_id for polling.
    202 Accepted is semantically correct — work is queued, not yet done.
    """
    task = sync_simplify_jobs.delay()
    return {"message": "Scrape job queued", "task_id": task.id}

# Status endpoint to check task progress
# @router.get("/sync-status/{task_id}")
# async def get_sync_status(task_id: str):
#     """Poll Celery task state by ID."""
#     from app.workers.celery_app import celery_app
#     task = celery_app.AsyncResult(task_id)
#     return {"task_id": task_id, "status": task.status, "result": task.result}