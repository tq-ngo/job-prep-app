from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from typing import Optional

from app.core.database import get_session
from app.models.job import Job
from app.schemas.job import JobRead, JobListResponse
from app.tasks.job_tasks import scrape_github, scrape_linkedin
from app.core.redis import get_redis_pool
from sqlalchemy import or_
import uuid

router = APIRouter()

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    # Query parameters with defaults and validation
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(default=None, description="Filter by source"),
    is_remote: Optional[bool] = Query(default=None),
    min_salary: Optional[int] = Query(default=None, ge=0),
    q: Optional[str] = Query(default=None, description="Search term for title or company"),
    category: Optional[str] = Query(default=None, description="Filter by category (FAANG+, Quant, Others)"),
    # FastAPI dependency injection: session is automatically managed
    session: AsyncSession = Depends(get_session),
):
    """
    List jobs with pagination and filtering.
    
    This is a standard paginated list endpoint. The offset pattern:
    - Page 1: OFFSET 0 LIMIT 20
    - Page 2: OFFSET 20 LIMIT 20
    - Page N: OFFSET (N-1)*page_size LIMIT page_size
    """
    offset = (page - 1) * page_size
    
    # Build query dynamically based on filters
    query = select(Job).where(Job.is_active == True)
    count_query = select(func.count(Job.id)).where(Job.is_active == True)
    
    if source:
        query = query.where(Job.source == source)
        count_query = count_query.where(Job.source == source)
    
    if is_remote is not None:
        query = query.where(Job.is_remote == is_remote)
        count_query = count_query.where(Job.is_remote == is_remote)
    
    if min_salary is not None:
        query = query.where(Job.salary_min >= min_salary)
        count_query = count_query.where(Job.salary_min >= min_salary)
    
    if q:
        search_filter = or_(Job.title.ilike(f"%{q}%"), Job.company.ilike(f"%{q}%"))
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if category:
        if category == "FAANG+":
            faang = ["facebook", "meta", "apple", "amazon", "netflix", "google", "microsoft", "nvidia"]
            faang_filter = or_(*[Job.company.op("~*")(f"\\b{c}\\b") for c in faang])
            query = query.where(faang_filter)
            count_query = count_query.where(faang_filter)
        elif category == "Quant":
            quant = ["jane street", "citadel", "two sigma", "hrt", "optiver", "jump trading"]
            quant_filter = or_(*[Job.company.op("~*")(f"\\b{c}\\b") for c in quant])
            query = query.where(quant_filter)
            count_query = count_query.where(quant_filter)
        elif category == "Others":
            faang_quant = ["facebook", "meta", "apple", "amazon", "netflix", "google", "microsoft", "nvidia", "jane street", "citadel", "two sigma", "hrt", "optiver", "jump trading"]
            others_filter = ~or_(*[Job.company.op("~*")(f"\\b{c}\\b") for c in faang_quant])
            query = query.where(others_filter)
            count_query = count_query.where(others_filter)

    # Order by date posted (latest on top)
    query = query.order_by(Job.posted_at.desc().nulls_last()).offset(offset).limit(page_size)
    
    # Execute both queries
    jobs_result = await session.execute(query)
    jobs = jobs_result.scalars().all()
    
    redis = await get_redis_pool()
    cache_key = f"jobs_count:{source}:{is_remote}:{min_salary}:{q}:{category}"
    cached_total = await redis.get(cache_key)
    
    if cached_total:
        total = int(cached_total)
    else:
        count_result = await session.execute(count_query)
        total = count_result.scalar()
        await redis.set(cache_key, total, ex=300)

    
    return JobListResponse(
        items=jobs,
        total=total,
        page=page,
        page_size=page_size,
        pages=(total + page_size - 1) // page_size,
    )


@router.post("/scrape/{source}", status_code=202)
async def trigger_scrape(source: str):
    """
    Trigger a background scrape job with an idempotency lock.
    """
    task_map = {
        "github": scrape_github,
        "linkedin": scrape_linkedin,
    }

    if source == "all":
        redis = await get_redis_pool()
        task_ids = []
        for src_name, src_task in task_map.items():
            lock_key = f"scrape_lock:{src_name}"
            acquired = await redis.set(lock_key, "locked", nx=True, ex=600)
            if acquired:
                task = src_task.delay() if src_name == "github" else src_task.delay("https://www.linkedin.com/jobs/search/?keywords=software+engineer")
                task_ids.append({"source": src_name, "task_id": task.id})
        if not task_ids:
            return {"status": "in_progress", "message": "All scrapers are already running."}
        return {
            "status": "accepted",
            "task_id": task_ids[0]["task_id"],
            "tasks": task_ids,
            "message": f"Triggered {len(task_ids)} scrapers",
        }
    
    if source not in task_map:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown source '{source}'. Valid: {list(task_map.keys()) + ['all']}"
        )
        
    redis = await get_redis_pool()
    lock_key = f"scrape_lock:{source}"
    
    acquired = await redis.set(lock_key, "locked", nx=True, ex=600)
    
    if not acquired:
        return {
            "status": "in_progress",
            "message": f"A scrape for {source} is already running."
        }
    
    if source == "linkedin":
        task = task_map[source].delay("https://www.linkedin.com/jobs/search/?keywords=software+engineer+intern")
    else:
        task = task_map[source].delay()
    
    return {
        "status": "accepted",
        "task_id": task.id,
        "message": f"Scraping {source} in background",
        "status_url": f"/api/v1/tasks/{task.id}",
    }


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    """Get a single job by ID."""
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job