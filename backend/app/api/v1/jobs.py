from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, func
from typing import Optional, List
import json

from app.core.database import get_session
from app.core.rate_limit import limiter
from app.models.job import Job
from app.models.users import User
from app.schemas.job import JobRead, JobListResponse, JobListItem
from app.tasks.job_tasks import scrape_github, scrape_linkedin
from app.core.redis import get_redis_pool
from app.api.v1.auth import get_current_user, require_csrf
from app.core.task_owner import record_task_owner
from app.scraping.sponsorship import classify_sponsorship
from sqlalchemy import or_, and_, case, Text
from sqlalchemy.orm import defer
import hashlib
import uuid

router = APIRouter()

POPULAR_TECH_SKILLS = [
    "Python", "React", "TypeScript", "JavaScript", "Java", "C++", "Go", "Rust",
    "C", "SQL", "PostgreSQL", "AWS", "Docker", "Kubernetes", "Linux", "Node.js",
    "GraphQL", "Next.js", "Tailwind CSS", "Redis", "Kafka", "PyTorch", "TensorFlow",
    "Spark", "FastAPI", "Django", "Flask", "Spring Boot", "Git", "CI/CD", "GCP",
    "Azure", "Terraform", "MongoDB", "NoSQL", "Pandas", "NumPy", "Swift", "Kotlin",
    "Android", "iOS", "Microservices", "REST APIs", "System Design", "Distributed Systems"
]


def to_job_list_item(j: Job) -> JobListItem:
    """Safely build a JobListItem using loaded attributes and description for sponsorship analysis."""
    spons = classify_sponsorship(j.title, getattr(j, "description", None) or "")
    loc = (j.location or "").lower()
    wt = "remote" if (j.is_remote or "remote" in loc) else ("hybrid" if "hybrid" in loc else "onsite")
    return JobListItem(
        id=j.id,
        external_id=j.external_id,
        source=j.source,
        source_url=j.source_url,
        title=j.title,
        company=j.company,
        location=j.location,
        apply_url=j.apply_url,
        salary_min=j.salary_min,
        salary_max=j.salary_max,
        salary_currency=j.salary_currency,
        salary_period=j.salary_period,
        category=j.category,
        skills=j.skills,
        seniority_level=j.seniority_level,
        employment_type=j.employment_type,
        is_remote=j.is_remote,
        work_type=wt,
        sponsorship_status=spons["status"],
        sponsorship_label=spons["label"],
        terms=j.terms,
        posted_at=j.posted_at,
        scraped_at=j.scraped_at,
        enriched_at=j.enriched_at,
        is_active=j.is_active,
    )


def to_job_read(j: Job) -> JobRead:
    """Safely build a JobRead for single-job drawer view with full description."""
    spons = classify_sponsorship(j.title, j.description or "")
    loc = (j.location or "").lower()
    wt = "remote" if (j.is_remote or "remote" in loc) else ("hybrid" if "hybrid" in loc else "onsite")
    return JobRead(
        id=j.id,
        external_id=j.external_id,
        source=j.source,
        source_url=j.source_url,
        title=j.title,
        company=j.company,
        location=j.location,
        description=j.description,
        apply_url=j.apply_url,
        salary_min=j.salary_min,
        salary_max=j.salary_max,
        salary_currency=j.salary_currency,
        salary_period=j.salary_period,
        category=j.category,
        skills=j.skills,
        seniority_level=j.seniority_level,
        employment_type=j.employment_type,
        is_remote=j.is_remote,
        work_type=wt,
        sponsorship_status=spons["status"],
        sponsorship_label=spons["label"],
        terms=j.terms,
        posted_at=j.posted_at,
        scraped_at=j.scraped_at,
        enriched_at=j.enriched_at,
        is_active=j.is_active,
    )


@router.get("/skills", response_model=List[str])
async def list_skills(
    q: Optional[str] = Query(default=None, max_length=50, description="Prefix or keyword to search"),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    """
    Suggests technical skills for autocomplete based on skills extracted from jobs.
    """
    redis = await get_redis_pool()
    cache_key = "popular_skills_cache"
    cached = await redis.get(cache_key)
    
    if cached:
        all_skills = json.loads(cached)
    else:
        # Fetch any distinct skills in DB
        result = await session.execute(
            select(Job.skills)
            .where(Job.is_active == True, Job.skills.is_not(None))
            .limit(100)
        )
        seen_skills = set(POPULAR_TECH_SKILLS)
        for row in result.scalars().all():
            if isinstance(row, list):
                for s in row:
                    if isinstance(s, str) and len(s) <= 40:
                        seen_skills.add(s.strip())
        all_skills = sorted(seen_skills, key=lambda s: s.lower())
        await redis.setex(cache_key, 600, json.dumps(all_skills))

    if not q or not q.strip():
        return all_skills[:limit]

    query = q.strip().lower()
    prefix_matches = [s for s in all_skills if s.lower().startswith(query)]
    substr_matches = [s for s in all_skills if query in s.lower() and not s.lower().startswith(query)]
    return (prefix_matches + substr_matches)[:limit]


@router.get("/", response_model=JobListResponse)
async def list_jobs(
    # Query parameters with defaults and validation
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=30, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(default=None, max_length=32, description="Filter by source"),
    is_remote: Optional[bool] = Query(default=None),
    min_salary: Optional[int] = Query(default=None, ge=0),
    q: Optional[str] = Query(default=None, max_length=200, description="Search term for title or company"),
    category: Optional[str] = Query(default=None, max_length=16, description="Filter by category (FAANG+, Quant, Others)"),
    work_type: Optional[str] = Query(default=None, max_length=16, description="Filter by work type (remote, hybrid, onsite)"),
    sponsorship: Optional[str] = Query(default=None, max_length=32, description="Filter by sponsorship (f1_eligible, h1b, requires_citizenship)"),
    skill: Optional[str] = Query(default=None, max_length=50, description="Filter by technical skill"),
    sort_by: Optional[str] = Query(default="date", max_length=16, description="Sort order (date, relevance)"),
    session: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user),
):
    offset = (page - 1) * page_size
    base_filters = [Job.is_active == True, Job.canonical_id.is_(None)]
    query = select(Job).options(defer(Job.embedding)).where(*base_filters)
    count_query = select(func.count(Job.id)).where(*base_filters)
    
    if source:
        query = query.where(Job.source == source)
        count_query = count_query.where(Job.source == source)
    
    if is_remote is not None:
        query = query.where(Job.is_remote == is_remote)
        count_query = count_query.where(Job.is_remote == is_remote)

    if work_type:
        wt = work_type.lower().strip()
        if wt == "remote":
            work_filter = or_(Job.is_remote == True, Job.location.ilike("%remote%"))
        elif wt == "hybrid":
            work_filter = or_(Job.location.ilike("%hybrid%"), Job.title.ilike("%hybrid%"))
        elif wt == "onsite":
            work_filter = and_(
                or_(Job.is_remote == False, Job.is_remote.is_(None)),
                or_(
                    Job.location.is_(None),
                    and_(~Job.location.ilike("%remote%"), ~Job.location.ilike("%hybrid%")),
                ),
            )
        else:
            work_filter = None
        if work_filter is not None:
            query = query.where(work_filter)
            count_query = count_query.where(work_filter)

    if sponsorship:
        sp = sponsorship.lower().strip()
        if sp in ("sponsorship_available", "f1_eligible", "cpt_opt", "h1b"):
            spons_filter = and_(
                ~Job.title.ilike("%citizen%"),
                ~Job.title.ilike("%clearance%"),
                ~Job.title.ilike("%itar%"),
                or_(
                    Job.title.ilike("%sponsor%"),
                    Job.title.ilike("%h1b%"),
                    Job.title.ilike("%h-1b%"),
                    Job.title.ilike("%cpt%"),
                    Job.title.ilike("%opt%"),
                    Job.description.ilike("%visa sponsorship%"),
                    Job.description.ilike("%sponsorship available%"),
                    Job.description.ilike("%h-1b%"),
                    Job.description.ilike("%cpt%"),
                    Job.description.ilike("%opt%"),
                ),
            )
        elif sp in ("requires_citizenship", "citizenship"):
            spons_filter = or_(
                Job.title.ilike("%citizen%"),
                Job.title.ilike("%clearance%"),
                Job.title.ilike("%itar%"),
                Job.description.ilike("%citizen%"),
                Job.description.ilike("%clearance%"),
                Job.description.ilike("%itar%"),
            )
        else:
            spons_filter = None
        if spons_filter is not None:
            query = query.where(spons_filter)
            count_query = count_query.where(spons_filter)

    if skill:
        sk_clean = skill.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").strip()
        skill_filter = or_(
            Job.skills.cast(Text).ilike(f'%"{sk_clean}"%', escape="\\"),
            Job.skills.cast(Text).ilike(f'%{sk_clean}%', escape="\\"),
            Job.title.ilike(f"%{sk_clean}%", escape="\\"),
        )
        query = query.where(skill_filter)
        count_query = count_query.where(skill_filter)
    
    if min_salary is not None:
        query = query.where(Job.salary_min >= min_salary)
        count_query = count_query.where(Job.salary_min >= min_salary)
    
    search_term = None
    if q:
        search_term = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_").strip()
        search_filter = or_(
            Job.title.ilike(f"%{search_term}%", escape="\\"),
            Job.company.ilike(f"%{search_term}%", escape="\\"),
            Job.skills.cast(Text).ilike(f'%{search_term}%', escape="\\"),
        )
        query = query.where(search_filter)
        count_query = count_query.where(search_filter)

    if category:
        query = query.where(Job.category == category)
        count_query = count_query.where(Job.category == category)

    MAX_UI_JOBS = 500  # All jobs are stored in DB; UI displays at most 500
    redis = await get_redis_pool()
    filter_digest = hashlib.sha256(
        "|".join(
            str(v) for v in (source, is_remote, min_salary, q, category, work_type, sponsorship, skill, sort_by)
        ).encode("utf-8")
    ).hexdigest()[:32]
    cache_key = f"jobs_count:{filter_digest}"
    cached_total = await redis.get(cache_key)

    if cached_total is not None:
        raw_total = int(cached_total)
    else:
        count_result = await session.execute(count_query)
        raw_total = count_result.scalar()
        await redis.set(cache_key, raw_total, ex=30)

    # Clamp display total to 500 — DB still holds all records
    total = min(raw_total, MAX_UI_JOBS)
    capped = raw_total > MAX_UI_JOBS
    pages = (total + page_size - 1) // page_size if total > 0 else 1

    if offset >= total:
        return JobListResponse(
            items=[],
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
            capped=capped,
        )

    remaining = total - offset
    if sort_by == "relevance":
        if search_term:
            query = query.order_by(
                case((Job.title.ilike(f"%{search_term}%", escape="\\"), 1), else_=2),
                Job.posted_at.desc().nulls_last(),
                Job.id
            )
        else:
            query = query.order_by(
                case((Job.category == "FAANG+", 1), (Job.category == "Quant", 2), else_=3),
                Job.posted_at.desc().nulls_last(),
                Job.id
            )
    else:
        query = query.order_by(Job.posted_at.desc().nulls_last(), Job.id)

    query = query.offset(offset).limit(min(page_size, remaining))

    jobs_result = await session.execute(query)
    jobs = jobs_result.scalars().all()
    items = [to_job_list_item(j) for j in jobs]
    
    return JobListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=pages,
        capped=capped,
    )


@router.post("/scrape/{source}", status_code=202)
@limiter.limit("10/minute")
async def trigger_scrape(
    request: Request,
    source: str,
    current_user: User = Depends(get_current_user),
    _: None = Depends(require_csrf),
):
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
        await record_task_owner([t["task_id"] for t in task_ids], current_user.id)
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
    await record_task_owner([task.id], current_user.id)

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
    return to_job_read(job)