import logging
import time
from datetime import timedelta
from typing import Any, Awaitable, Callable, Dict, List, Set, Tuple

from cachetools import LRUCache
from sqlalchemy import func, literal_column, select, text, tuple_, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.datetime_utils import utc_now
from app.core.events import KIND_CREATED, job_event_payload, publish_job_event
from app.core.redis import create_worker_redis
from app.models.job import Job
from app.scraping.categorize import categorize, company_domain
from app.scraping.dedup import dedup_engine

logger = logging.getLogger(__name__)

Key = Tuple[str, str]  # (external_id, source)

# Layer 1: per-process LRU of job keys known to be fully synced (row exists
# AND description extraction was attempted). Sized for several days' crawls.
_seen_jobs_cache: LRUCache = LRUCache(maxsize=25_000)

# Layer 2: Redis sorted set, member = "source:external_id", score = epoch
# seconds when last confirmed synced. A plain SET with EXPIRE on the whole
# key never expired at all — every crawl (every 6h) pushed the 90-day TTL
# forward, so it grew forever. Scores give each entry its own expiry.
_SEEN_ZSET = "seen:jobs"
_SEEN_TTL_SECONDS = 90 * 24 * 3600

# Columns that a re-crawl is allowed to refresh. Built per-batch from the keys
# actually present, because `stmt.excluded.<col>` for a column absent from the
# INSERT resolves to DEFAULT (NULL) — which would wipe a backfilled
# description on the next crawl.
_UPDATABLE_COLUMNS = (
    "title", "company", "location", "salary_min", "salary_max",
    "apply_url", "source_url", "is_remote", "scraped_at", "is_active",
    "canonical_hash", "category", "company_domain",
)

# A posting whose description couldn't be fetched (403/404, JS-only page) is
# not retried until this long after the attempt. Without it every crawl
# re-fetched each unreachable posting, 3 backoff retries apiece — ~half of a
# second crawl's wall time in a live run was spent on 117 permanent failures.
JD_RETRY_AFTER = timedelta(days=7)

DescriptionFetcher = Callable[[List[Dict[str, Any]]], Awaitable[int]]


def _key(record: Dict[str, Any]) -> Key:
    return (str(record.get("external_id")), str(record.get("source")))


def _member(key: Key) -> str:
    return f"{key[1]}:{key[0]}"


class DatabaseSyncService:
    """
    Sync a crawled batch through a sequential 3-layer dedup pipeline, and
    only then spend network on job-description extraction.

        L1  in-process LRU   ─ hit ─┐
         │ miss                      │
        L2  Redis ZSET       ─ hit ─┤──▶ known: touch scraped_at/is_active
         │ miss                      │
        L3  PostgreSQL       ─ hit ─┘    (unless the row still lacks a JD)
         │ miss
        new ──▶ fetch JD ──▶ UPSERT ──▶ link cross-source duplicates

    Previously the crawlers fetched a description for EVERY record before
    this service ran, so dedup saved no network at all: each crawl re-fetched
    every posting's JD, and large GitHub runs could outlive their lock.

    Dedup is keyed on (source, external_id) only. The content fingerprint
    (company|title|location) is used to LINK cross-source duplicates via
    canonical_id, never to skip: skipping on it silently dropped genuinely
    distinct reqs that share a title and location.

    L1/L2 are advisory. Their hits are confirmed with one COUNT against L3,
    so a restored or truncated database can't leave postings permanently
    "seen" and missing.
    """

    def __init__(self, session: AsyncSession):
        self.session = session

    async def sync_batch(
        self,
        job_records: List[Dict[str, Any]],
        fetch_descriptions: DescriptionFetcher,
    ) -> Dict[str, int]:
        """
        Sync one crawled batch. `fetch_descriptions` fills `description` in
        place on the records it is given and returns how many it filled.

        Returns {"inserted", "updated", "skipped", "linked", "descriptions"}.
        "skipped" counts postings already fully synced (only touched).
        """
        stats = {"inserted": 0, "updated": 0, "skipped": 0, "linked": 0, "descriptions": 0}
        if not job_records:
            return stats

        records = self._collapse_intra_batch(job_records)
        self._attach_fingerprints(records)

        redis = create_worker_redis()
        try:
            known = await self._known_from_cache(records, redis)
            needs_upsert, already_synced, existing = await self._classify_in_db(records, known)

            if already_synced:
                stats["skipped"] = await self._touch(already_synced)

            inserted_ids: List[Any] = []
            if needs_upsert:
                stats["descriptions"] = await fetch_descriptions(needs_upsert)
                # Stamp EVERY attempt, successful or not: it is what lets
                # _lookup_existing skip recently-failed postings.
                now = utc_now()
                for r in needs_upsert:
                    r["description_fetched_at"] = now
                inserted_ids = await self._upsert(needs_upsert)
                stats["inserted"] = len(inserted_ids)
                stats["updated"] = len(needs_upsert) - stats["inserted"]

            hashes = {r["canonical_hash"] for r in records if r.get("canonical_hash")}
            stats["linked"] = await self.relink_hashes(hashes)
            await self.session.commit()

            await self._publish_created(inserted_ids, redis)

            # A cache hit must mean "nothing left to fetch for this posting",
            # so a failed fetch stays uncached and is retried next crawl until
            # backfill_descriptions stamps it as attempted.
            await self._mark_synced(
                [_key(r) for r in already_synced]
                + [_key(r) for r in needs_upsert if r.get("description")],
                redis,
            )
            return stats
        finally:
            await redis.aclose()

    # ── L1 + L2 ─────────────────────────────────────────────────────────

    async def _known_from_cache(self, records: List[Dict[str, Any]], redis) -> Set[Key]:
        keys = [_key(r) for r in records]
        known = {k for k in keys if k in _seen_jobs_cache}           # L1

        l2_candidates = [k for k in keys if k not in known]
        if l2_candidates:                                             # L2
            cutoff = time.time() - _SEEN_TTL_SECONDS
            scores = await redis.zmscore(_SEEN_ZSET, [_member(k) for k in l2_candidates])
            for k, score in zip(l2_candidates, scores):
                if score is not None and float(score) >= cutoff:
                    known.add(k)
                    _seen_jobs_cache[k] = True  # promote to L1
        return known

    # ── L3 ──────────────────────────────────────────────────────────────

    async def _classify_in_db(
        self, records: List[Dict[str, Any]], known: Set[Key]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], Set[Key]]:
        """
        Split records into (needs_upsert, already_synced, keys_existing_in_db).

        Cache hits are confirmed with one COUNT; if any is missing from the
        DB, the caches are stale and every record falls through to the
        per-row L3 lookup.
        """
        if known:
            present = await self._count_existing(list(known))
            if present < len(known):
                logger.warning(
                    "Dedup cache stale: %d of %d cached keys missing from DB; "
                    "falling through to L3 and purging them",
                    len(known) - present, len(known),
                )
                for k in known:
                    _seen_jobs_cache.pop(k, None)
                known = set()

        unknown = [_key(r) for r in records if _key(r) not in known]
        existing = await self._lookup_existing(unknown) if unknown else {}

        needs_upsert, already_synced = [], []
        for r in records:
            k = _key(r)
            if k in known or existing.get(k):
                already_synced.append(r)
            else:
                # New, or a pre-JD-extraction row whose description was never
                # attempted: worth one fetch.
                needs_upsert.append(r)
        return needs_upsert, already_synced, set(existing) | known

    async def _lookup_existing(self, keys: List[Key]) -> Dict[Key, bool]:
        """Map each key present in the DB to whether its JD needs no fetch now."""
        retry_cutoff = utc_now() - JD_RETRY_AFTER
        rows = await self.session.execute(
            select(
                Job.external_id,
                Job.source,
                (Job.description.isnot(None) | (Job.description_fetched_at > retry_cutoff)),
            ).where(tuple_(Job.external_id, Job.source).in_(keys))
        )
        return {(eid, src): attempted for eid, src, attempted in rows}

    async def _count_existing(self, keys: List[Key]) -> int:
        stmt = select(func.count()).select_from(Job).where(
            tuple_(Job.external_id, Job.source).in_(keys)
        )
        return (await self.session.execute(stmt)).scalar_one()

    async def _touch(self, records: List[Dict[str, Any]]) -> int:
        """
        Refresh scraped_at and reactivate postings seen again.

        The old pipeline skipped known postings entirely, so a job that was
        deactivated and later reappeared in a README stayed hidden forever.
        """
        keys = [_key(r) for r in records]
        await self.session.execute(
            update(Job)
            .where(tuple_(Job.external_id, Job.source).in_(keys))
            .values(scraped_at=utc_now(), is_active=True)
        )
        return len(keys)

    @staticmethod
    def _collapse_intra_batch(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Collapse duplicate (external_id, source) within one batch.

        Postgres raises CardinalityViolationError if a single INSERT ... ON
        CONFLICT touches the same conflict target twice.
        """
        deduped: Dict[Key, Dict[str, Any]] = {}
        for r in records:
            deduped[_key(r)] = r
        return list(deduped.values())

    @staticmethod
    def _attach_fingerprints(records: List[Dict[str, Any]]) -> None:
        """Attach the content fingerprint plus ingest-time classification."""
        for r in records:
            company, title = r.get("company") or "", r.get("title") or ""
            if company and title:
                r["canonical_hash"] = dedup_engine.generate_fingerprint(
                    company, title, r.get("location") or ""
                )
            r["category"] = categorize(company, title)
            r["company_domain"] = company_domain(r.get("apply_url"))

    async def _upsert(self, records: List[Dict[str, Any]]) -> List[Any]:
        """UPSERT the records; returns ids of rows that were newly INSERTED."""
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
        if "description_source" in all_keys:
            update_cols["description_source"] = func.coalesce(
                stmt.excluded.description_source, Job.description_source
            )
        # posted_at is deliberately excluded: relative dates ("3 days ago") are
        # recomputed at crawl time, so refreshing it would drift the date
        # forward on every re-scrape.

        result = await self.session.execute(
            stmt.on_conflict_do_update(
                constraint="uq_jobs_external_id_source", set_=update_cols
            ).returning(
                Job.id,
                # A row created by this statement has xmax = 0; one updated by
                # ON CONFLICT has xmax = this transaction's id.
                literal_column("(xmax = 0)").label("inserted"),
            )
        )
        return [row.id for row in result if row.inserted]

    async def _publish_created(self, inserted_ids: List[Any], redis) -> None:
        """
        Emit `created` events for new postings that are visible in the feed.

        Runs after commit and after linking, so a new row that turned out to
        duplicate an existing posting (canonical_id set) doesn't announce
        itself as a new job.
        """
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
                # Live updates are best-effort; the rows are already committed.
                logger.warning("Failed to publish created event for %s: %s", job.id, exc)

    # ── Cross-source linking ────────────────────────────────────────────

    async def relink_hashes(self, hashes: Set[str]) -> int:
        """
        Recompute canonical_id for every row sharing one of these hashes.

        The canonical row is the earliest-seen ACTIVE one. Previously it was
        the earliest by scraped_at regardless of is_active, and a row that
        became canonical never had its own canonical_id cleared — so when the
        original posting was deactivated, its still-active duplicate stayed
        linked to it and vanished from the feed (which filters on
        `is_active AND canonical_id IS NULL`). Call this after any change to
        is_active as well as after inserts.

        Does not commit. Returns the number of rows whose link changed.
        """
        if not hashes:
            return 0
        result = await self.session.execute(
            text(
                """
                WITH ranked AS (
                    SELECT id,
                           FIRST_VALUE(id) OVER (
                               PARTITION BY canonical_hash
                               ORDER BY is_active DESC, first_seen_at, id
                           ) AS canonical
                    FROM jobs
                    WHERE canonical_hash = ANY(:hashes)
                )
                UPDATE jobs j
                SET canonical_id = CASE WHEN r.id = r.canonical THEN NULL ELSE r.canonical END
                FROM ranked r
                WHERE j.id = r.id
                  AND j.canonical_id IS DISTINCT FROM
                      (CASE WHEN r.id = r.canonical THEN NULL ELSE r.canonical END)
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
        # Prune expired entries; O(log N + M), cheap enough to do per batch.
        pipe.zremrangebyscore(_SEEN_ZSET, "-inf", now - _SEEN_TTL_SECONDS)
        await pipe.execute()
        for k in keys:
            _seen_jobs_cache[k] = True
