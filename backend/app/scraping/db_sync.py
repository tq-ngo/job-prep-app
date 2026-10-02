import logging
from typing import Any, Dict, List, Optional

from cachetools import LRUCache
from sqlalchemy import func, select, text, tuple_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import create_worker_redis
from app.models.job import Job
from app.scraping.dedup import dedup_engine

logger = logging.getLogger(__name__)

# Layer 1: per-worker in-memory cache of "(source, external_id)" and "canonical_hash".
# Sized for a day's crawl (~500 jobs) plus headroom.
_seen_jobs_cache: LRUCache = LRUCache(maxsize=25_000)
_seen_hashes_cache: LRUCache = LRUCache(maxsize=25_000)

# Redis keys. Both carry 90-day TTL.
_SEEN_KEY = "global_seen_jobs"
_SEEN_HASHES_KEY = "global_seen_hashes"
_SEEN_TTL_SECONDS = 90 * 24 * 3600  # 90 days

# Columns that a re-crawl is allowed to refresh. Built per-batch from the keys
# actually present, because `stmt.excluded.<col>` for a column absent from the
# INSERT resolves to DEFAULT (NULL) — which would wipe a backfilled
# description on the next crawl.
_UPDATABLE_COLUMNS = (
    "title", "company", "location", "salary_min", "salary_max",
    "apply_url", "source_url", "is_remote", "scraped_at", "is_active",
    "canonical_hash",
)


class DatabaseSyncService:
    """
    Bulk asynchronous PostgreSQL UPSERT with a 3-layer deduplication pipeline.

        Layer 1  in-process LRU        (O(1), no network)
        Layer 2  Redis set             (O(1), shared across workers)
        Layer 3  ON CONFLICT DO UPDATE (durable source of truth)

    Cross-source duplicates (the same role posted to both GitHub and LinkedIn)
    are resolved by a content fingerprint, but NON-DESTRUCTIVELY: every row is
    inserted, and later matches get `canonical_id` pointing at the first. The
    previous implementation checked a TTL-less Redis set and silently dropped
    the incoming job, so genuinely distinct reqs sharing a company/title/
    location (e.g. 40 Amazon "SWE Intern, Seattle" postings) collapsed into a
    single row forever, with no way to recover them or to tell the two cases
    apart.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def bulk_upsert_jobs(self, job_records: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Upsert a batch of scraped job dicts.

        Returns a breakdown {"inserted", "updated", "skipped", "linked"}.
        The old version returned `result.rowcount` — which for
        ON CONFLICT DO UPDATE counts inserts AND updates — and the caller
        reported it as "new", inflating the count shown in the UI.
        """
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "linked": 0}
        if not job_records:
            return stats

        redis = create_worker_redis()
        try:
            self._attach_fingerprints(job_records)
            candidates = await self._filter_already_synced(job_records, redis, stats)
            if not candidates:
                logger.info("All %d jobs in batch already synced.", len(job_records))
                return stats

            candidates = self._collapse_intra_batch(candidates)

            before = await self._count_existing(candidates)
            await self._upsert(candidates)
            after = await self._count_existing(candidates)

            stats["inserted"] = after - before
            stats["updated"] = len(candidates) - stats["inserted"]

            stats["linked"] = await self._link_cross_source_duplicates(candidates)
            await self._mark_synced(candidates, redis)
            return stats
        finally:
            await redis.aclose()

    # ── Layers 1 & 2 ────────────────────────────────────────────────────

    async def _filter_already_synced(
        self, records: List[Dict[str, Any]], redis, stats: Dict[str, int]
    ) -> List[Dict[str, Any]]:
        """
        Drop records already known to this worker (L1 LRU) or cluster (L2 Redis).

        Evaluates both (source:external_id) and composite canonical_hash
        (company|title|location). A record carrying a newly-extracted description
        always falls through so descriptions can be backfilled.
        """
        keys = [f"{r.get('source')}:{r.get('external_id')}" for r in records]
        hashes = [r.get("canonical_hash") or "" for r in records]

        # Single round-trip pipelined checks
        pipe = redis.pipeline()
        if keys:
            pipe.smismember(_SEEN_KEY, keys)
        if any(hashes):
            pipe.smismember(_SEEN_HASHES_KEY, [h for h in hashes if h])
        
        results = await pipe.execute() if keys else []
        membership_keys = results[0] if results else []
        hash_results = results[1] if len(results) > 1 else []
        hash_map = dict(zip([h for h in hashes if h], hash_results)) if hash_results else {}

        out: List[Dict[str, Any]] = []
        for record, key, in_redis_key in zip(records, keys, membership_keys):
            chash = record.get("canonical_hash")
            in_redis_hash = hash_map.get(chash, False) if chash else False
            in_l1 = (key in _seen_jobs_cache) or (chash and chash in _seen_hashes_cache)
            in_l2 = in_redis_key or in_redis_hash

            carries_new_content = bool(record.get("description"))
            if not carries_new_content and (in_l1 or in_l2):
                _seen_jobs_cache[key] = True
                if chash:
                    _seen_hashes_cache[chash] = True
                stats["skipped"] += 1
                continue
            out.append(record)
        return out

    @staticmethod
    def _collapse_intra_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collapse duplicate (external_id, source) within one batch.

        Postgres raises CardinalityViolationError if a single INSERT ... ON
        CONFLICT touches the same conflict target twice.
        """
        deduped: Dict[Any, Dict[str, Any]] = {}
        for r in records:
            deduped[(r.get("external_id"), r.get("source"))] = r
        return list(deduped.values())

    @staticmethod
    def _attach_fingerprints(records: List[Dict[str, Any]]) -> None:
        for r in records:
            company, title = r.get("company") or "", r.get("title") or ""
            if company and title:
                r["canonical_hash"] = dedup_engine.generate_fingerprint(
                    company, title, r.get("location") or ""
                )

    # ── Layer 3 ─────────────────────────────────────────────────────────

    async def _count_existing(self, records: List[Dict[str, Any]]) -> int:
        """Count how many of these (external_id, source) pairs already exist."""
        pairs = [(r.get("external_id"), r.get("source")) for r in records]
        if not pairs:
            return 0
        stmt = select(func.count()).select_from(Job).where(
            tuple_(Job.external_id, Job.source).in_(pairs)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def _upsert(self, records: List[Dict[str, Any]]) -> None:
        # insert().values(list_of_dicts) uses the FIRST dict's keys for the
        # column list, so normalize every record to the same key set.
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
        # Never overwrite a stored description with NULL. A crawl that didn't
        # fetch the JD (or whose fetch failed) must leave the existing one
        # intact; coalesce keeps the incoming value only when it is non-null.
        if "description" in all_keys:
            update_cols["description"] = func.coalesce(
                stmt.excluded.description, Job.description
            )
            update_cols["description_fetched_at"] = func.coalesce(
                stmt.excluded.description_fetched_at, Job.description_fetched_at
            )
        # posted_at is deliberately excluded: relative dates ("3 days ago") are
        # recomputed at crawl time, so refreshing it would drift the date
        # forward on every re-scrape.

        await self.session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_jobs_external_id_source", set_=update_cols
            )
        )
        await self.session.commit()

    async def _link_cross_source_duplicates(self, records: List[Dict[str, Any]]) -> int:
        """
        Point every non-first row sharing a canonical_hash at the earliest one.

        Runs in SQL so it stays correct regardless of which batch or crawler
        inserted the rows. Nothing is deleted; the feed collapses duplicates
        by filtering `canonical_id IS NULL`.
        """
        hashes = sorted({r["canonical_hash"] for r in records if r.get("canonical_hash")})
        if not hashes:
            return 0

        result = await self.session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT id,
                           FIRST_VALUE(id) OVER (
                               PARTITION BY canonical_hash
                               ORDER BY scraped_at, id
                           ) AS canonical,
                           canonical_hash
                    FROM jobs
                    WHERE canonical_hash = ANY(:hashes)
                )
                UPDATE jobs j
                SET canonical_id = r.canonical
                FROM ranked r
                WHERE j.id = r.id
                  AND r.id <> r.canonical
                  AND j.canonical_id IS DISTINCT FROM r.canonical
                """
            ),
            {"hashes": hashes},
        )
        await self.session.commit()
        return result.rowcount or 0

    # ── Cache population ────────────────────────────────────────────────

    async def _mark_synced(self, records: List[Dict[str, Any]], redis) -> None:
        keys = [f"{r.get('source')}:{r.get('external_id')}" for r in records]
        hashes = [r.get("canonical_hash") for r in records if r.get("canonical_hash")]
        if not keys:
            return

        pipe = redis.pipeline()
        pipe.sadd(_SEEN_KEY, *keys)
        pipe.expire(_SEEN_KEY, _SEEN_TTL_SECONDS)
        if hashes:
            pipe.sadd(_SEEN_HASHES_KEY, *hashes)
            pipe.expire(_SEEN_HASHES_KEY, _SEEN_TTL_SECONDS)
        await pipe.execute()

        for key in keys:
            _seen_jobs_cache[key] = True
        for h in hashes:
            _seen_hashes_cache[h] = True
