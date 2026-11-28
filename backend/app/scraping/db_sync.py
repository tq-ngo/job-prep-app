import logging
import time
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, List, Set, Tuple

from cachetools import LRUCache
from sqlalchemy import and_, case, func, literal_column, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.events import KIND_CREATED, job_event_payload, publish_job_event
from app.core.redis import create_worker_cache_redis, create_worker_redis
from app.models.job import Job
from app.scraping.categorize import categorize, company_domain
from app.scraping.dedup import dedup_engine
from app.scraping.sponsorship import classify_sponsorship

logger = logging.getLogger(__name__)

Key = Tuple[str, str]  # (external_id, source)

# Layer 1: per-process LRU of job keys known to be fully synced WITH a description.
_seen_jobs_cache: LRUCache = LRUCache(maxsize=25_000)

# Layer 2: Redis sorted set in cache Redis, member = "source:external_id", score = epoch.
_SEEN_ZSET = "seen:jobs"
_SEEN_TTL_SECONDS = 90 * 24 * 3600

# O(1) version counter for jobs_count cache keys (replaces blocking KEYS scan).
JOBS_COUNT_VERSION_KEY = "jobs_count:ver"

_UPDATABLE_COLUMNS = (
    "title", "company", "location", "salary_min", "salary_max",
    "apply_url", "source_url", "is_remote", "scraped_at", "is_active",
    "canonical_hash", "category", "company_domain",
    "sponsorship_status", "sponsorship_label",
)

JD_RETRY_AFTER = timedelta(days=7)

DescriptionFetcher = Callable[[List[Dict[str, Any]]], Awaitable[int]]

_RELINK_LOCK_KEY = 0x6A6F_6273_7265_6C6E  # "jobsreln"


def _key(record: Dict[str, Any]) -> Key:
    return (str(record.get("external_id")), str(record.get("source")))


def _member(key: Key) -> str:
    return f"{key[1]}:{key[0]}"


async def invalidate_jobs_count_cache(redis) -> None:
    """O(1) invalidation of cached count totals via version counter bump."""
    try:
        await redis.incr(JOBS_COUNT_VERSION_KEY)
    except Exception as exc:
        logger.warning("Failed to invalidate jobs_count cache: %s", exc)


class DatabaseSyncService:
    """
    Sync a crawled batch through a sequential 3-layer dedup pipeline before
    spending network on job-description extraction.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_batch(
        self,
        job_records: List[Dict[str, Any]],
        fetch_descriptions: DescriptionFetcher,
    ) -> Dict[str, int]:
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "linked": 0, "descriptions": 0}
        if not job_records:
            return stats

        records = self._collapse_intra_batch(job_records)
        self._attach_fingerprints(records)

        state_redis = create_worker_redis()
        cache_redis = create_worker_cache_redis()
        try:
            known = await self._known_from_cache(records, cache_redis)
            needs_upsert, already_synced, cacheable_existing = await self._classify_in_db(
                records, known, cache_redis
            )

            reactivated_hashes: Set[str] = set()
            if already_synced:
                touched, reactivated_hashes = await self._touch(already_synced)
                stats["skipped"] = touched
                if reactivated_hashes:
                    # Relink reactivated postings in the same transaction as _touch
                    # so no feed query observes an unlinked reactivated duplicate.
                    stats["linked"] += await self.relink_hashes(reactivated_hashes)

            # End the transaction before network fetches.
            await self.session.commit()

            inserted_ids: List[Any] = []
            if needs_upsert:
                stats["descriptions"] = await fetch_descriptions(needs_upsert)
                now = utc_now()
                for r in needs_upsert:
                    r["description_fetched_at"] = now
                    spons = classify_sponsorship(r.get("title") or "", r.get("description") or "")
                    r["sponsorship_status"] = spons["status"]
                    r["sponsorship_label"] = spons["label"]
                inserted_ids = await self._upsert(needs_upsert)
                stats["inserted"] = len(inserted_ids)
                stats["updated"] = len(needs_upsert) - stats["inserted"]

                hashes = {r["canonical_hash"] for r in needs_upsert if r.get("canonical_hash")}
                stats["linked"] += await self.relink_hashes(hashes)
                await self.session.commit()

            await self._publish_created(inserted_ids, state_redis)

            if inserted_ids or stats["linked"] or reactivated_hashes:
                await invalidate_jobs_count_cache(cache_redis)

            # Only cache keys that actually HAVE a description in L1/L2 `seen:jobs`.
            # Rows whose JD failed stay out of the 90-day cache so JD_RETRY_AFTER (7d)
            # retries them cleanly once their cooldown elapses.
            keys_to_cache = list(cacheable_existing) + [
                _key(r) for r in needs_upsert if r.get("description")
            ]
            await self._mark_synced(keys_to_cache, cache_redis)
            return stats
        finally:
            await state_redis.aclose(close_connection_pool=True)
            await cache_redis.aclose(close_connection_pool=True)

    # ── L1 + L2 ─────────────────────────────────────────────────────────

    async def _known_from_cache(self, records: List[Dict[str, Any]], redis) -> Set[Key]:
        keys = [_key(r) for r in records]
        known = {k for k in keys if k in _seen_jobs_cache}

        l2_candidates = [k for k in keys if k not in known]
        if l2_candidates:
            cutoff = time.time() - _SEEN_TTL_SECONDS
            scores = await redis.zmscore(_SEEN_ZSET, [_member(k) for k in l2_candidates])
            for k, score in zip(l2_candidates, scores):
                if score is not None and float(score) >= cutoff:
                    known.add(k)
                    _seen_jobs_cache[k] = True
        return known

    # ── L3 ──────────────────────────────────────────────────────────────

    async def _classify_in_db(
        self, records: List[Dict[str, Any]], known: Set[Key], cache_redis=None
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Set[Key]]:
        """
        Split records into (needs_upsert, already_synced, cacheable_keys).
        `cacheable_keys` contains ONLY keys confirmed to have a non-null description.
        """
        if known:
            present = await self._count_existing(list(known))
            if present < len(known):
                logger.warning(
                    "Dedup cache stale: %d of %d cached keys missing from DB; "
                    "falling through to L3 and purging L1/L2",
                    len(known) - present, len(known),
                )
                for k in known:
                    _seen_jobs_cache.pop(k, None)
                if cache_redis is not None:
                    try:
                        await cache_redis.zrem(_SEEN_ZSET, *[_member(k) for k in known])
                    except Exception as exc:
                        logger.warning("Failed to purge stale keys from %s: %s", _SEEN_ZSET, exc)
                known = set()

        unknown = [_key(r) for r in records if _key(r) not in known]
        existing = await self._lookup_existing(unknown) if unknown else {}

        needs_upsert, already_synced = [], []
        cacheable_keys: Set[Key] = set(known)
        for r in records:
            k = _key(r)
            if k in known:
                already_synced.append(r)
            elif k in existing:
                skip_fetch, has_desc = existing[k]
                if skip_fetch:
                    already_synced.append(r)
                    if has_desc:
                        cacheable_keys.add(k)
                else:
                    needs_upsert.append(r)
            else:
                needs_upsert.append(r)
        return needs_upsert, already_synced, cacheable_keys

    async def _lookup_existing(self, keys: List[Key]) -> Dict[Key, Tuple[bool, bool]]:
        """
        Map each key present in the DB to `(skip_jd_fetch_now, has_description)`.
        """
        retry_cutoff = utc_now() - JD_RETRY_AFTER
        rows = await self.session.execute(
            select(
                Job.external_id,
                Job.source,
                Job.description.isnot(None),
                (Job.description.isnot(None) | (Job.description_fetched_at > retry_cutoff)),
            ).where(tuple_(Job.external_id, Job.source).in_(keys))
        )
        return {(eid, src): (bool(skip_now), bool(has_desc)) for eid, src, has_desc, skip_now in rows}

    async def _count_existing(self, keys: List[Key]) -> int:
        stmt = select(func.count()).select_from(Job).where(
            tuple_(Job.external_id, Job.source).in_(keys)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def _touch(self, records: List[Dict[str, Any]]) -> Tuple[int, Set[str]]:
        """
        Refresh scraped_at and reactivate postings seen again.
        Returns `(touched_count, reactivated_canonical_hashes)`.
        """
        keys = [_key(r) for r in records]
        # Capture hashes of rows that were inactive so caller can relink & invalidate count cache.
        inactive_hashes = {
            h
            for h in (
                await self.session.execute(
                    select(Job.canonical_hash)
                    .where(tuple_(Job.external_id, Job.source).in_(keys))
                    .where(Job.is_active == False)  # noqa: E712
                )
            ).scalars().all()
            if h
        }
        await self.session.execute(
            update(Job)
            .where(tuple_(Job.external_id, Job.source).in_(keys))
            .values(scraped_at=utc_now(), is_active=True)
        )
        return len(keys), inactive_hashes

    @staticmethod
    def _collapse_intra_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        deduped: Dict[Key, Dict[str, Any]] = {}
        for r in records:
            deduped[_key(r)] = r
        return list(deduped.values())

    @staticmethod
    def _attach_fingerprints(records: List[Dict[str, Any]]) -> None:
        for r in records:
            company, title = r.get("company") or "", r.get("title") or ""
            if company and title:
                r["canonical_hash"] = dedup_engine.generate_fingerprint(
                    company, title, r.get("location") or ""
                )
            r["category"] = categorize(company, title)
            r["company_domain"] = company_domain(r.get("apply_url"))
            spons = classify_sponsorship(title, r.get("description") or "")
            r["sponsorship_status"] = spons["status"]
            r["sponsorship_label"] = spons["label"]

    async def _upsert(self, records: List[Dict[str, Any]]) -> List[Any]:
        all_keys = set()
        for r in records:
            all_keys.update(r.keys())
        rows = [{k: r.get(k) for k in all_keys} for r in records]

        stmt = insert(Job).values(rows)

        update_cols = {
            col: getattr(stmt.excluded, col)
            for col in _UPDATABLE_COLUMNS
            if col in all_keys
        }
        if "description" in all_keys:
            update_cols["description"] = func.coalesce(
                stmt.excluded.description, Job.description
            )
            update_cols["description_fetched_at"] = func.coalesce(
                stmt.excluded.description_fetched_at, Job.description_fetched_at
            )
            update_cols["sponsorship_status"] = func.coalesce(
                stmt.excluded.sponsorship_status, Job.sponsorship_status
            )
            update_cols["sponsorship_label"] = func.coalesce(
                stmt.excluded.sponsorship_label, Job.sponsorship_label
            )
            update_cols["scrape_status"] = case(
                (
                    and_(Job.description.is_(None), stmt.excluded.description.isnot(None)),
                    "raw",
                ),
                else_=Job.scrape_status,
            )
        if "description_source" in all_keys:
            update_cols["description_source"] = func.coalesce(
                stmt.excluded.description_source, Job.description_source
            )

        result = await self.session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_jobs_external_id_source", set_=update_cols
            ).returning(
                Job.id,
                literal_column("(xmax = 0)").label("inserted"),
            )
        )
        return [row.id for row in result if row.inserted]

    async def _publish_created(self, inserted_ids: List[Any], redis) -> None:
        if not inserted_ids:
            return
        rows = (await self.session.execute(
            select(Job)
            .where(Job.id.in_(inserted_ids))
            .where(Job.is_active == True)  # noqa: E712
            .where(Job.canonical_id.is_(None))
        )).scalars().all()
        for job in rows:
            try:
                await publish_job_event(redis, job_event_payload(job, KIND_CREATED))
            except Exception as exc:
                logger.warning("Failed to publish created event for %s: %s", job.id, exc)

    # ── Cross-source linking ────────────────────────────────────────────

    async def relink_hashes(self, hashes: Set[str]) -> int:
        if not hashes:
            return 0
        await self.session.execute(
            text("SELECT pg_advisory_xact_lock(:key)"), {"key": _RELINK_LOCK_KEY}
        )
        result = await self.session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT id,
                           source,
                           apply_url,
                           FIRST_VALUE(id) OVER (
                               PARTITION BY canonical_hash
                               ORDER BY is_active DESC, first_seen_at, id
                           ) AS canonical_id_candidate,
                           FIRST_VALUE(source) OVER (
                               PARTITION BY canonical_hash
                               ORDER BY is_active DESC, first_seen_at, id
                           ) AS canonical_source,
                           FIRST_VALUE(apply_url) OVER (
                               PARTITION BY canonical_hash
                               ORDER BY is_active DESC, first_seen_at, id
                           ) AS canonical_apply_url,
                           ROW_NUMBER() OVER (
                               PARTITION BY canonical_hash, source
                               ORDER BY is_active DESC, first_seen_at, id
                           ) AS source_rank
                    FROM jobs
                    WHERE canonical_hash = ANY(:hashes)
                ),
                resolved AS (
                    SELECT id,
                           CASE
                               WHEN id = canonical_id_candidate THEN NULL
                               WHEN source = canonical_source THEN
                                   CASE WHEN apply_url = canonical_apply_url THEN canonical_id_candidate ELSE NULL END
                               WHEN source_rank = 1 THEN canonical_id_candidate
                               ELSE NULL
                           END AS new_canonical_id
                    FROM ranked
                )
                UPDATE jobs j
                SET canonical_id = r.new_canonical_id
                FROM resolved r
                WHERE j.id = r.id
                  AND j.canonical_id IS DISTINCT FROM r.new_canonical_id
                """
            ),
            {"hashes": sorted(hashes)},
        )
        return result.rowcount or 0

    # ── Cache population ────────────────────────────────────────────────

    async def _mark_synced(self, keys: List[Key], redis) -> None:
        if not keys:
            return
        now = time.time()
        pipe = redis.pipeline()
        pipe.zadd(_SEEN_ZSET, {_member(k): now for k in keys})
        pipe.zremrangebyscore(_SEEN_ZSET, "-inf", now - _SEEN_TTL_SECONDS)
        await pipe.execute()
        for k in keys:
            _seen_jobs_cache[k] = True
