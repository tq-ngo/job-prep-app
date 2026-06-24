import asyncio
import json
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from app.core.database import get_session
from app.api.deps import get_current_user
from app.models.jobs import JobApplication, Job, Company
from app.models.users import User
from app.workers.tasks import sync_simplify_jobs, sync_linkedin_jobs
from app.workers.celery_app import celery_app
from app.services.search_service import SearchService
from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from typing import List, Optional, Dict, Any

router = APIRouter()

class JobApplicationResponse(BaseModel):
    id: UUID
    company_name: str
    job_title: str
    job_url: str
    location: Optional[str] = None
    source: str
    status: str
    date_applied: datetime

class JobSearchResponse(BaseModel):
    id: UUID
    company_name: str
    job_title: str
    apply_url: str
    location: Optional[str] = None
    skills_required: List[str] = []
    remote_policy: str
    salary_min_usd: Optional[int] = None
    salary_max_usd: Optional[int] = None
    quality_score: int
    posted_at: datetime

@router.get("/", response_model=List[JobApplicationResponse])
async def read_jobs(
    skip: int = 0,
    limit: int = 100,
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """
    Returns jobs application status mapped to the user.
    Joins JobApplication with Job and Company to provide metadata for UI.
    """
    stmt = (
        select(JobApplication, Job, Company)
        .join(Job, JobApplication.job_id == Job.id)
        .join(Company, Job.company_id == Company.id)
        .where(JobApplication.user_id == current_user.id)
        .offset(skip)
        .limit(limit)
    )
    result = await session.execute(stmt)
    rows = result.all()
    
    response_data = []
    for app, job, company in rows:
        response_data.append({
            "id": app.id,
            "company_name": company.name,
            "job_title": job.title_normalized,
            "job_url": job.apply_url,
            "location": job.location_city,
            "source": job.source_urls[0] if job.source_urls else "Unknown",
            "status": app.status,
            "date_applied": app.date_applied
        })
    return response_data

@router.get("/search", response_model=List[JobSearchResponse])
async def search_jobs(
    q: Optional[str] = None,
    skills: Optional[str] = None,  # comma-separated list
    remote_only: bool = False,
    min_salary: Optional[int] = None,
    skip: int = 0,
    limit: int = 20,
    session: AsyncSession = Depends(get_session)
):
    """
    High-performance faceted job search.
    Tries Elasticsearch primary index first, falls back gracefully to DB query if ES is down.
    """
    skills_list = [s.strip() for s in skills.split(",")] if skills else None
    search_service = SearchService()
    
    es_results = search_service.search_jobs(
        query=q,
        skills=skills_list,
        remote_only=remote_only,
        min_salary=min_salary,
        skip=skip,
        limit=limit
    )
    
    if es_results is not None:
        hits = es_results.get("hits", {}).get("hits", [])
        response_data = []
        for hit in hits:
            source = hit.get("_source", {})
            response_data.append({
                "id": UUID(hit["_id"]),
                "company_name": source.get("company", "Unknown"),
                "job_title": source.get("title", "Unknown"),
                "apply_url": source.get("apply_url", ""),
                "location": source.get("location"),
                "skills_required": source.get("skills", []),
                "remote_policy": source.get("remote_policy", "onsite"),
                "salary_min_usd": source.get("salary_min_usd"),
                "salary_max_usd": source.get("salary_max_usd"),
                "quality_score": source.get("quality_score", 0),
                "posted_at": datetime.fromisoformat(source["posted_at"]) if source.get("posted_at") else datetime.utcnow()
            })
        return response_data

    # Fallback to standard PostgreSQL relational query
    stmt = select(Job, Company).join(Company).where(Job.is_active == True)
    
    if q:
        stmt = stmt.where(Job.title_normalized.ilike(f"%{q}%") | Job.description_text.ilike(f"%{q}%"))
    if remote_only:
        stmt = stmt.where(Job.remote_policy == "remote")
    if min_salary:
        stmt = stmt.where(Job.salary_min_usd >= min_salary)
        
    stmt = stmt.offset(skip).limit(limit)
    result = await session.execute(stmt)
    rows = result.all()
    
    return [
        {
            "id": job.id,
            "company_name": company.name,
            "job_title": job.title_normalized,
            "apply_url": job.apply_url,
            "location": f"{job.location_city or ''}, {job.location_country or ''}".strip(", "),
            "skills_required": job.skills_required or [],
            "remote_policy": job.remote_policy,
            "salary_min_usd": job.salary_min_usd,
            "salary_max_usd": job.salary_max_usd,
            "quality_score": job.quality_score,
            "posted_at": job.first_seen_at
        }
        for job, company in rows
    ]

@router.post("/trigger-sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_scraping_pipeline(current_user: User = Depends(get_current_user)):
    """
    Enqueues a background scrape job for Simplify via Celery.
    """
    task = sync_simplify_jobs.delay(str(current_user.id))
    return {"message": "Simplify scrape job queued", "task_id": task.id}

@router.post("/trigger-linkedin-sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_linkedin_scraping(
    search_url: str,
    current_user: User = Depends(get_current_user)
):
    """
    Enqueues a background LinkedIn scrape job via Celery.
    """
    task = sync_linkedin_jobs.delay(str(current_user.id), search_url)
    return {"message": "LinkedIn scrape job queued", "task_id": task.id}

@router.get("/sync-status/{task_id}")
async def get_sync_status(task_id: str):
    """Poll Celery task state by ID."""
    task = celery_app.AsyncResult(task_id)
    return {"task_id": task_id, "status": task.status, "result": task.result}

@router.get("/sync-stream/{task_id}")
async def sync_stream(task_id: str):
    """
    Server-Sent Events endpoint to stream Celery task progress.
    """
    async def event_generator():
        while True:
            task = celery_app.AsyncResult(task_id)
            
            # Extract state and meta/result
            data = {
                "status": task.status,
                "message": "",
                "task_id": task_id
            }
            
            if task.status == 'PROGRESS':
                data["message"] = task.info.get("message", "Processing...")
            elif task.status == 'SUCCESS':
                data["message"] = str(task.result)
                yield f"data: {json.dumps(data)}\n\n"
                break
            elif task.status == 'FAILURE':
                data["message"] = str(task.info)
                yield f"data: {json.dumps(data)}\n\n"
                break
            
            yield f"data: {json.dumps(data)}\n\n"
            
            if task.ready():
                break
                
            await asyncio.sleep(1) # Wait 1 second between updates

    return StreamingResponse(event_generator(), media_type="text/event-stream")

@router.post("/{job_id}/track", status_code=status.HTTP_201_CREATED)
async def track_global_job(
    job_id: UUID,
    status_str: str = "Applied",
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
):
    """
    Saves a global job to the user's tracking list (JobApplication).
    """
    stmt = select(Job).where(Job.id == job_id)
    res = await session.execute(stmt)
    job = res.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    stmt = select(JobApplication).where(JobApplication.job_id == job_id, JobApplication.user_id == current_user.id)
    res = await session.execute(stmt)
    app = res.scalar_one_or_none()
    if app:
        return {"message": "Job is already being tracked", "application_id": app.id}

    db_app = JobApplication(
        user_id=current_user.id,
        job_id=job_id,
        status=status_str,
        date_applied=datetime.utcnow()
    )
    session.add(db_app)
    await session.commit()
    await session.refresh(db_app)
    return {"message": "Job tracked successfully", "application_id": db_app.id}
