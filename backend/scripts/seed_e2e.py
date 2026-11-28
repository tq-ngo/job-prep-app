"""
Seed script for Playwright E2E smoke tests.
Seeds a test user and sample job listings into the E2E database.
"""
import asyncio
import sys
from pathlib import Path

# Ensure backend root is on sys.path so `app` can be imported regardless of invocation cwd
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlmodel import select
from app.core.database import create_worker_session_ctx
from app.models.users import User
from app.models.job import Job
from app.core.security import get_password_hash
from app.core.datetime_utils import utc_now


async def seed():
    async with create_worker_session_ctx() as session:
        # 1. Seed or update test user
        email = "playwright-smoke@example.com".strip().lower()
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        hashed = get_password_hash("SmokePassword123!")

        if not user:
            user = User(
                email=email,
                hashed_password=hashed,
                full_name="Playwright Smoke Tester",
                is_active=True,
            )
            session.add(user)
        else:
            user.hashed_password = hashed
            user.is_active = True
            session.add(user)

        # 2. Seed sample jobs for category and search interactions
        jobs_data = [
            {
                "external_id": "e2e-faang-1",
                "source": "github",
                "source_url": "https://github.com/simplify-jobs/Summer2026-Internships",
                "title": "Software Engineer Intern",
                "company": "Google",
                "location": "Mountain View, CA",
                "category": "FAANG+",
                "sponsorship_status": "sponsorship_available",
                "sponsorship_label": "Sponsorship Available",
                "company_domain": "google.com",
                "apply_url": "https://careers.google.com/jobs/1",
                "description": "Google is looking for Software Engineer Interns to join our team for Summer 2026.",
                "is_active": True,
                "scrape_status": "enriched",
                "posted_at": utc_now(),
            },
            {
                "external_id": "e2e-quant-1",
                "source": "github",
                "source_url": "https://github.com/simplify-jobs/Summer2026-Internships",
                "title": "Quantitative Trading Intern",
                "company": "Jane Street",
                "location": "New York, NY",
                "category": "Quant",
                "sponsorship_status": "sponsorship_available",
                "sponsorship_label": "Sponsorship Available",
                "company_domain": "janestreet.com",
                "apply_url": "https://janestreet.com/jobs/1",
                "description": "Jane Street is looking for Quantitative Trading Interns.",
                "is_active": True,
                "scrape_status": "enriched",
                "posted_at": utc_now(),
            },
        ]

        for jd in jobs_data:
            stmt = select(Job).where(Job.external_id == jd["external_id"], Job.source == jd["source"])
            existing = (await session.execute(stmt)).scalar_one_or_none()
            if not existing:
                job = Job(**jd)
                session.add(job)
            else:
                for k, v in jd.items():
                    setattr(existing, k, v)
                session.add(existing)

        await session.commit()
        print("E2E database successfully seeded!")


if __name__ == "__main__":
    asyncio.run(seed())
