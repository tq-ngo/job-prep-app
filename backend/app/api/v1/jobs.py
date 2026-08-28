from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from typing import Optional

from app.core.database import get_session
from app.models.job import Job
from app.models.users import User
from app.schemas.job import JobRead, JobListResponse
from app.tasks.job_tasks import scrape_github, scrape_linkedin
from app.core.redis import get_redis_pool
from app.api.v1.auth import get_current_user
from sqlalchemy import or_
import uuid

router = APIRouter()

@router.get("/", response_model=JobListResponse)
async def list_jobs(
    # Query parameters with defaults and validation
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=30, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(default=None, description="Filter by source"),
    is_remote: Optional[bool] = Query(default=None),
    min_salary: Optional[int] = Query(default=None, ge=0),
    q: Optional[str] = Query(default=None, description="Search term for title or company"),
    category: Optional[str] = Query(default=None, description="Filter by category (FAANG+, Quant, Others)"),
    # FastAPI dependency injection: session is automatically managed
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
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
        faang = ["meta", "apple", "amazon", "netflix", "google", "microsoft", "nvidia", "tesla", "tiktok", "bytedance"]
        faang_filter = or_(*[Job.company.ilike(f"%{c}%") for c in faang])
        
        quant_companies = [
            "jane street", "citadel", "two sigma", "hrt", "hudson river trading", 
            "optiver", "jump trading", "akuna", "drw", "imc", "tower research", 
            "point72", "deshaw", "de shaw", "renaissance", "susquehanna", "sig"
        ]
        quant_roles = ["quant", "quantitative", "algo", "trading", "hft"]
        quant_filter = or_(
            *[Job.company.ilike(f"%{c}%") for c in quant_companies],
            *[Job.title.ilike(f"%{r}%") for r in quant_roles]
        )

        if category == "FAANG+":
            query = query.where(faang_filter)
            count_query = count_query.where(faang_filter)
        elif category == "Quant":
            query = query.where(quant_filter)
            count_query = count_query.where(quant_filter)
        elif category == "Others":
            others_filter = ~or_(faang_filter, quant_filter)
            query = query.where(others_filter)
            count_query = count_query.where(others_filter)


    MAX_UI_JOBS = 500  # All jobs are stored in DB; UI displays at most 500
    redis = await get_redis_pool()
    cache_key = f"jobs_count:{source}:{is_remote}:{min_salary}:{q}:{category}"
    cached_total = await redis.get(cache_key)
    
    if cached_total:
        raw_total = int(cached_total)
    else:
        count_result = await session.execute(count_query)
        raw_total = count_result.scalar()
        await redis.set(cache_key, raw_total, ex=30)
    
    # Clamp display total to 500 — DB still holds all records
    total = min(raw_total, MAX_UI_JOBS)
    pages = (total + page_size - 1) // page_size if total > 0 else 1
    
    if offset >= total:
        return JobListResponse(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )

    # Order by date posted (latest on top), apply pagination
    query = query.order_by(Job.posted_at.desc().nulls_last()).offset(offset).limit(page_size)
    
    # Execute data query
    jobs_result = await session.execute(query)
    jobs = jobs_result.scalars().all()
    
    return JobListResponse(
        items=jobs,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
    )


@router.post("/scrape/{source}", status_code=202)
async def trigger_scrape(source: str, current_user: User = Depends(get_current_user)):
    """
    Trigger a background scrape job. Idempotency is handled inside each
    task via Redis NX locks — the API simply dispatches and
    the task will self-skip if already running.
    """
    task_map = {
        "github": scrape_github,
        "linkedin": scrape_linkedin,
    }

    if source == "all":
        task_ids = []
        for src_name, src_task in task_map.items():
            task = src_task.delay() if src_name == "github" else src_task.delay(
                "https://www.linkedin.com/jobs/search/?keywords=software+engineer+intern"
            )
            task_ids.append({"source": src_name, "task_id": task.id})
        combined_task_id = ",".join([t["task_id"] for t in task_ids])
        return {
            "status": "accepted",
            "task_id": combined_task_id,
            "tasks": task_ids,
            "message": f"Triggered {len(task_ids)} scrapers (each will self-skip if already running)",
        }
    
    if source not in task_map:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown source '{source}'. Valid: {list(task_map.keys()) + ['all']}"
        )

    if source == "linkedin":
        task = task_map[source].delay("https://www.linkedin.com/jobs/search/?keywords=software+engineer+intern")
    else:
        task = task_map[source].delay()
    
    return {
        "status": "accepted",
        "task_id": task.id,
        "message": f"Scraping {source} in background (will self-skip if already running)",
        "status_url": f"/api/v1/tasks/{task.id}",
    }


@router.get("/{job_id}", response_model=JobRead)
async def get_job(job_id: uuid.UUID, session: AsyncSession = Depends(get_session), current_user: User = Depends(get_current_user)):
    """Get a single job by ID."""
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job