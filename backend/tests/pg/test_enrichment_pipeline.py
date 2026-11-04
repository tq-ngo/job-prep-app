"""
The enrichment claim protocol and the pipeline SQL that only Postgres can
run: SKIP LOCKED claims, ON CONFLICT status resets, array binds, advisory
locks. Task bodies are called directly with a stub `self`, against the real
database, with Gemini and Redis replaced.
"""
import uuid
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, text, update

from app.ai.gemini_client import GeminiConfigError, GeminiThrottled
from app.ai.skill_extractor import JobAttributes
from app.config import settings
from app.core.datetime_utils import utc_now
from app.core.events import JOBS_STREAM
from app.models.job import Job
from app.scraping.db_sync import DatabaseSyncService
from app.tasks import job_tasks

pytestmark = pytest.mark.pg


def _job(**overrides) -> Job:
    n = uuid.uuid4().hex[:8]
    fields = dict(
        external_id=f"ext-{n}",
        source="github",
        title="SWE Intern",
        company=f"Acme {n}",
        apply_url=f"https://acme.example/jobs/{n}",
        description="Build things in Python and React.",
    )
    return Job(**{**fields, **overrides})


async def _insert(engine, *jobs: Job) -> None:
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine, expire_on_commit=False) as s:
        s.add_all(jobs)
        await s.commit()


async def _fetch(engine, job_id) -> Job:
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(engine) as s:
        return (await s.execute(select(Job).where(Job.id == job_id))).scalar_one()


async def _claim(engine, job_id) -> str:
    """Claim a job the way process_raw_jobs_batch does; return the token."""
    async with engine.begin() as conn:
        queued_at = (await conn.execute(
            text("UPDATE jobs SET scrape_status='queued', queued_at=clock_timestamp()"
                 " WHERE id=:id RETURNING queued_at"),
            {"id": job_id},
        )).scalar_one()
    return queued_at.isoformat()


def _task(retries: int = 0):
    task = MagicMock()
    task.request.retries = retries
    task.request.id = "test-task"
    task.max_retries = 2
    task.retry.side_effect = RuntimeError("retry")
    return task


@pytest.fixture
def gemini(fake_redis):
    """Stub Gemini and point the task's Redis at the shared fake."""
    extract = AsyncMock(return_value=JobAttributes(skills=["python", "react"]))
    embed = AsyncMock(return_value=[0.1] * 768)
    slots = AsyncMock()
    with patch.object(job_tasks, "extract_job_attributes", extract), patch.object(
        job_tasks, "generate_embedding", embed
    ), patch.object(job_tasks, "acquire_gemini_slots", slots), patch.object(
        job_tasks, "create_worker_redis", return_value=fake_redis
    ):
        yield MagicMock(extract=extract, embed=embed, slots=slots)


async def _events(fake_redis) -> list:
    return await fake_redis.xrange(JOBS_STREAM)


# ── Claim protocol ──────────────────────────────────────────────────────

async def test_duplicate_messages_enrich_once(worker_db, gemini, fake_redis):
    job = _job()
    await _insert(worker_db, job)
    claim = await _claim(worker_db, job.id)

    first = await job_tasks._enrich_job_with_ai(_task(), str(job.id), claim)
    second = await job_tasks._enrich_job_with_ai(_task(), str(job.id), claim)

    assert (first, second) == ("enriched", "skipped")
    assert gemini.extract.await_count == 1
    assert len(await _events(fake_redis)) == 1
    row = await _fetch(worker_db, job.id)
    assert row.scrape_status == "enriched"
    assert row.skills == ["python", "react"]
    assert row.queued_at is None


async def test_stale_claim_after_reclaim_does_nothing(worker_db, gemini, fake_redis):
    job = _job()
    await _insert(worker_db, job)
    stale = await _claim(worker_db, job.id)
    await _claim(worker_db, job.id)  # reaper requeued it and it was claimed again

    assert await job_tasks._enrich_job_with_ai(_task(), str(job.id), stale) == "skipped"
    gemini.extract.assert_not_awaited()


async def test_claim_lost_mid_flight_discards_result(worker_db, gemini, fake_redis):
    job = _job()
    await _insert(worker_db, job)
    claim = await _claim(worker_db, job.id)

    async def reclaimed_meanwhile(*_):
        await _claim(worker_db, job.id)
        return JobAttributes(skills=["go"])

    gemini.extract.side_effect = reclaimed_meanwhile
    assert await job_tasks._enrich_job_with_ai(_task(), str(job.id), claim) == "superseded"
    assert await _events(fake_redis) == []
    row = await _fetch(worker_db, job.id)
    assert row.scrape_status == "queued" and row.skills is None


async def test_duplicate_rows_are_enriched_but_not_announced(worker_db, gemini, fake_redis):
    primary = _job()
    await _insert(worker_db, primary)
    dup = _job(canonical_id=primary.id)
    await _insert(worker_db, dup)
    claim = await _claim(worker_db, dup.id)

    assert await job_tasks._enrich_job_with_ai(_task(), str(dup.id), claim) == "enriched"
    assert await _events(fake_redis) == []


async def test_throttled_job_goes_back_to_raw_without_a_retry(worker_db, gemini):
    job = _job()
    await _insert(worker_db, job)
    claim = await _claim(worker_db, job.id)
    gemini.slots.side_effect = GeminiThrottled("budget", retry_after=20)
    task = _task()

    assert await job_tasks._enrich_job_with_ai(task, str(job.id), claim) == "throttled"
    task.retry.assert_not_called()
    gemini.extract.assert_not_awaited()
    assert (await _fetch(worker_db, job.id)).scrape_status == "raw"


async def test_config_error_fails_loudly_and_releases_the_job(worker_db, gemini):
    job = _job()
    await _insert(worker_db, job)
    claim = await _claim(worker_db, job.id)
    gemini.extract.side_effect = GeminiConfigError("model not found")
    task = _task()

    with pytest.raises(GeminiConfigError):
        await job_tasks._enrich_job_with_ai(task, str(job.id), claim)
    task.retry.assert_not_called()
    assert (await _fetch(worker_db, job.id)).scrape_status == "raw"


async def test_unexpected_error_parks_job_after_last_retry(worker_db, gemini):
    job = _job()
    await _insert(worker_db, job)
    claim = await _claim(worker_db, job.id)
    gemini.extract.side_effect = ValueError("bad response")

    with pytest.raises(ValueError):
        await job_tasks._enrich_job_with_ai(_task(retries=2), str(job.id), claim)
    assert (await _fetch(worker_db, job.id)).scrape_status == "failed"


# ── Claiming ────────────────────────────────────────────────────────────

async def test_batch_tops_queue_up_to_capacity(worker_db, monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_RATE_LIMIT", "2/m")  # capacity = 2/m x 2 min = 4
    await _insert(worker_db, *[_job() for _ in range(8)])
    already = _job()
    await _insert(worker_db, already)
    await _claim(worker_db, already.id)

    with patch.object(job_tasks.enrich_job_with_ai, "delay") as delay:
        result = await job_tasks._process_raw_jobs_batch(_task(), batch_size=10)

    assert result == "Enqueued 3 jobs for enrichment"
    # Every message carries the claim it was enqueued under.
    for call in delay.call_args_list:
        job_id, claim = call.args
        row = await _fetch(worker_db, uuid.UUID(job_id))
        assert row.scrape_status == "queued"
        assert row.queued_at.isoformat() == claim

    with patch.object(job_tasks.enrich_job_with_ai, "delay") as delay:
        assert (await job_tasks._process_raw_jobs_batch(_task())).startswith("Queue full")
    delay.assert_not_called()


# ── db_sync SQL ─────────────────────────────────────────────────────────

async def test_late_description_sends_job_back_to_enrichment(worker_db):
    from sqlalchemy.ext.asyncio import AsyncSession

    job = _job(description=None, scrape_status="enriched")
    await _insert(worker_db, job)

    async with AsyncSession(worker_db) as s:
        await DatabaseSyncService(s)._upsert([{
            "external_id": job.external_id, "source": job.source, "title": job.title,
            "company": job.company, "apply_url": job.apply_url,
            "description": "Now we know what the job is.", "description_fetched_at": utc_now(),
        }])
        await s.commit()

    row = await _fetch(worker_db, job.id)
    assert row.description == "Now we know what the job is."
    assert row.scrape_status == "raw"


async def test_recrawl_without_description_keeps_status(worker_db):
    from sqlalchemy.ext.asyncio import AsyncSession

    job = _job(scrape_status="enriched")
    await _insert(worker_db, job)
    async with AsyncSession(worker_db) as s:
        await DatabaseSyncService(s)._upsert([{
            "external_id": job.external_id, "source": job.source, "title": job.title,
            "company": job.company, "apply_url": job.apply_url, "description": None,
        }])
        await s.commit()

    row = await _fetch(worker_db, job.id)
    assert row.scrape_status == "enriched"
    assert row.description == job.description


async def test_github_deactivation_binds_ids_as_one_array(worker_db):
    from sqlalchemy.ext.asyncio import AsyncSession

    readme = "https://raw.githubusercontent.com/x/README.md"
    kept, dropped = _job(source_url=readme), _job(source_url=readme)
    await _insert(worker_db, kept, dropped)

    # Far past asyncpg's 32,767 bind-parameter ceiling.
    seen = [kept.external_id] + [f"other-{i}" for i in range(40_000)]
    async with AsyncSession(worker_db) as s:
        count = await job_tasks.deactivate_unseen_github(DatabaseSyncService(s), [readme], seen)
        await s.commit()

    assert count == 1
    assert (await _fetch(worker_db, kept.id)).is_active is True
    assert (await _fetch(worker_db, dropped.id)).is_active is False


async def test_stale_linkedin_rows_retire_and_hand_over_canonical(worker_db):
    from app.scraping.dedup import dedup_engine

    h = dedup_engine.generate_fingerprint("Acme", "SWE Intern", "NYC")
    old = utc_now() - timedelta(days=30)
    stale = _job(source="linkedin", canonical_hash=h, scraped_at=old, first_seen_at=old)
    fresh = _job(source="github", canonical_hash=h)
    await _insert(worker_db, stale, fresh)
    async with worker_db.begin() as conn:
        await conn.execute(update(Job).where(Job.id == fresh.id).values(canonical_id=stale.id))

    result = await job_tasks._deactivate_stale_jobs(_task(), "linkedin", 21)

    assert result == "Deactivated 1"
    assert (await _fetch(worker_db, stale.id)).is_active is False
    # The GitHub duplicate becomes the canonical, feed-visible row.
    assert (await _fetch(worker_db, fresh.id)).canonical_id is None
