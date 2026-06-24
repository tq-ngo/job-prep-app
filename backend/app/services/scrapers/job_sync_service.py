import uuid
import urllib.parse
import hashlib
from datetime import datetime
from typing import List, Dict, Any
from uuid import UUID
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session, select

from app.core.database import sync_engine, async_engine
from app.models.jobs import Company, Job, JobApplication
from app.services.search_service import SearchService


def clean_domain(company_name: str, url: str) -> str:
    try:
        parsed = urllib.parse.urlparse(url)
        netloc = parsed.netloc.lower()
        if netloc.startswith("www."):
            netloc = netloc[4:]
        # filter out generic platforms
        generic = ["greenhouse.io", "lever.co", "simplify.jobs", "github.com", "linkedin.com", "indeed.com"]
        if any(g in netloc for g in generic):
            name_part = company_name.lower().strip().replace(" ", "").replace(",", "").replace(".", "")
            return f"{name_part}.com"
        return netloc
    except Exception:
        name_part = company_name.lower().strip().replace(" ", "").replace(",", "").replace(".", "")
        return f"{name_part}.com"


def get_content_fingerprint(company_name: str, title: str, location: str) -> str:
    normalized = (
        company_name.lower().strip(),
        title.lower().strip().replace("sr.", "senior").replace("swe", "software engineer"),
        location.lower().strip()
    )
    return hashlib.sha256("|".join(normalized).encode()).hexdigest()[:32]


class JobSyncService:
    """
    Handles all DB persistence for scraped jobs.
    Completely decoupled from scraping logic — accepts plain dicts.
    """

    def sync_jobs_sync(self, jobs: List[Dict[str, str]], user_id: str) -> int:
        """
        Synchronous version of job sync, ideal for Celery workers.
        Handles normalization, deduplication, SQL Model inserts, and Elasticsearch indexing.
        """
        if not jobs:
            return 0

        user_uuid = uuid.UUID(user_id)
        search_service = SearchService()

        # Step 1: Extract and upsert Companies
        companies_data = {}
        for job in jobs:
            cname = job.get("company_name", "Unknown").strip()
            curl = job.get("job_url", "")
            domain = clean_domain(cname, curl)
            companies_data[domain] = cname

        with Session(sync_engine) as session:
            # Upsert Companies
            for domain, name in companies_data.items():
                stmt = insert(Company).values(
                    name=name,
                    domain=domain,
                    created_at=datetime.utcnow()
                ).on_conflict_do_nothing(index_elements=["domain"])
                session.exec(stmt)
            session.commit()

            # Retrieve Company IDs for referencing
            domains_list = list(companies_data.keys())
            stmt = select(Company).where(Company.domain.in_(domains_list))
            companies = session.exec(stmt).all()
            company_map = {c.domain: c.id for c in companies}

            # Step 2: Build global jobs catalog objects
            fingerprinted_jobs = {}
            for job in jobs:
                cname = job.get("company_name", "Unknown").strip()
                curl = job.get("job_url", "")
                domain = clean_domain(cname, curl)
                comp_id = company_map.get(domain)
                if not comp_id:
                    continue
                
                title = job.get("job_title", "").strip()
                loc = job.get("location", "").strip()
                fingerprint = get_content_fingerprint(cname, title, loc)
                
                if fingerprint not in fingerprinted_jobs:
                    fingerprinted_jobs[fingerprint] = {
                        "company_id": comp_id,
                        "title_raw": title,
                        "title_normalized": title,
                        "seniority": "mid",
                        "skills_required": [],
                        "skills_preferred": [],
                        "salary_min_usd": None,
                        "salary_max_usd": None,
                        "salary_currency": "USD",
                        "remote_policy": "remote" if "remote" in loc.lower() or "remote" in title.lower() else "onsite",
                        "location_city": loc,
                        "location_country": "US", # Default fallback
                        "visa_sponsorship": False,
                        "equity": False,
                        "apply_url": curl,
                        "content_fingerprint": fingerprint,
                        "quality_score": 0,
                        "is_active": True,
                        "source_urls": [curl],
                        "external_ids": {},
                        "first_seen_at": datetime.utcnow(),
                        "last_seen_at": datetime.utcnow(),
                        "created_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                else:
                    if curl not in fingerprinted_jobs[fingerprint]["source_urls"]:
                        fingerprinted_jobs[fingerprint]["source_urls"].append(curl)

            # Upsert global Job catalog
            for fingerprint, job_fields in fingerprinted_jobs.items():
                stmt = insert(Job).values(job_fields)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["content_fingerprint"],
                    set_={
                        "last_seen_at": datetime.utcnow(),
                        "updated_at": datetime.utcnow()
                    }
                )
                session.exec(stmt)
            session.commit()

            # Retrieve updated Job catalog records to fetch IDs
            stmt = select(Job).where(Job.content_fingerprint.in_(list(fingerprinted_jobs.keys())))
            jobs_db = session.exec(stmt).all()
            job_map = {j.content_fingerprint: j for j in jobs_db}

            # Step 3: Insert user JobApplications mapping to local user_id
            apps_to_insert = []
            for fingerprint, job_fields in fingerprinted_jobs.items():
                j_record = job_map.get(fingerprint)
                if j_record:
                    apps_to_insert.append({
                        "user_id": user_uuid,
                        "job_id": j_record.id,
                        "status": "Applied",
                        "date_applied": datetime.utcnow()
                    })

            if apps_to_insert:
                stmt = insert(JobApplication).values(apps_to_insert).on_conflict_do_nothing(index_elements=["job_id", "user_id"])
                session.exec(stmt)
                session.commit()

            # Step 4: Index to Elasticsearch for faceted searches
            for j_record in jobs_db:
                company_record = next((c for c in companies if c.id == j_record.company_id), None)
                company_name = company_record.name if company_record else "Unknown Company"
                
                job_data = {
                    "title_raw": j_record.title_raw,
                    "title_normalized": j_record.title_normalized,
                    "company_name": company_name,
                    "description_text": j_record.description_text or "",
                    "skills_required": j_record.skills_required or [],
                    "seniority": j_record.seniority,
                    "remote_policy": j_record.remote_policy,
                    "location_city": j_record.location_city,
                    "location_country": j_record.location_country,
                    "salary_min_usd": j_record.salary_min_usd,
                    "salary_max_usd": j_record.salary_max_usd,
                    "quality_score": j_record.quality_score,
                    "is_active": j_record.is_active,
                    "first_seen_at": j_record.first_seen_at.isoformat() if j_record.first_seen_at else ""
                }
                search_service.index_job(str(j_record.id), job_data)

        return len(jobs)

    async def sync_jobs_async(self, jobs: List[Dict[str, str]], user_id: UUID) -> int:
        """
        Asynchronous wrapper to mimic sync persistence behavior.
        Runs synchronous implementation in a threadpool to avoid locking the event loop.
        """
        import asyncio
        loop = asyncio.get_running_loop()
        # Run sync_jobs_sync on thread executor
        return await loop.run_in_executor(None, self.sync_jobs_sync, jobs, str(user_id))
