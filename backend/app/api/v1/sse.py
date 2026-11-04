"""
Server-Sent Events hub for live job-board updates.

Rewritten from Redis pub/sub to a Redis **Stream**. Pub/sub is fire-and-forget
with no backlog, and the endpoint emitted no `id:` field and never read
`Last-Event-ID`, so every event published while a client was reconnecting
(1-30s of exponential backoff) was lost permanently and invisibly. A stream
gives each event a durable id, so a reconnecting client resumes exactly where
it left off.

Auth moved from a `?token=` query parameter to the HttpOnly cookie that
EventSource sends automatically with `withCredentials`. The query parameter
put a long-lived credential into nginx access logs, browser history and
Referer headers.
"""
import asyncio
import json
import logging
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth_cookies import ACCESS_COOKIE, is_payload_revoked
from app.core.database import AsyncSessionLocal, get_session
from app.core.events import JOBS_STREAM, KIND_ENRICHED, publish_job_event  # noqa: F401 (re-export)
from app.core.redis import create_worker_redis, get_redis_pool
from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter()

SSE_KEEPALIVE_SECONDS = 25
# Re-check the token periodically: a connection previously outlived token
# expiry for up to nginx's proxy_read_timeout (24h) because auth was only
# ever validated once, at connect.
AUTH_RECHECK_SECONDS = 60

# Each stream pins a dedicated Redis connection for its whole life, so an
# unbounded number per user was an easy way to exhaust Redis. Three covers a
# few open tabs; useJobAlerts shares one stream per tab.
MAX_STREAMS_PER_USER = 3
# Live streams refresh their entry every read (<= SSE_KEEPALIVE_SECONDS), so
# an entry this old belongs to a stream whose process died without cleanup.
_STREAM_STALE_SECONDS = SSE_KEEPALIVE_SECONDS * 3
_STREAMS_PREFIX = "sse:streams:"

# A Redis stream entry id. Anything else made XREAD raise, which closed the
# stream; the client reconnected with the same bad id until it gave up.
_STREAM_ID_RE = re.compile(r"^\d{1,20}-\d{1,20}$")

# Session factory for the periodic re-check, which runs after the request's
# own dependency-scoped session has closed. A module attribute so tests can
# point it elsewhere.
_session_factory = AsyncSessionLocal


def _authorize(raw_token: Optional[str]) -> dict:
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return decode_token(raw_token, TOKEN_TYPE_ACCESS)
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def _is_active_user(session: AsyncSession, email: str) -> bool:
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    return user is not None and user.is_active


async def _register_stream(redis, user_key: str, stream_id: str) -> bool:
    """Count this stream against the user's cap; False if over it.

    Add-then-count rather than count-then-add, so two simultaneous connects
    can't both squeeze into the last slot.
    """
    key = _STREAMS_PREFIX + user_key
    now = time.time()
    async with redis.pipeline(transaction=True) as pipe:
        pipe.zadd(key, {stream_id: now})
        pipe.zremrangebyscore(key, "-inf", now - _STREAM_STALE_SECONDS)
        pipe.zcard(key)
        pipe.expire(key, _STREAM_STALE_SECONDS)
        _, _, count, _ = await pipe.execute()
    if count > MAX_STREAMS_PER_USER:
        await redis.zrem(key, stream_id)
        return False
    return True


def sanitize_last_event_id(raw: Optional[str]) -> Optional[str]:
    """Return a usable stream cursor, or None to start from new events."""
    return raw if raw and _STREAM_ID_RE.match(raw) else None


async def job_event_generator(
    request: Request,
    user_skills: set,
    raw_token: str,
    last_event_id: Optional[str],
    user_key: str,
    stream_id: str,
):
    """
    Yield SSE frames from the Redis stream, resuming after `last_event_id`.

    Uses a dedicated Redis connection rather than the shared API pool: each
    SSE client holds its connection open for the life of the stream, so at
    ~50 concurrent viewers the shared 50-connection pool was exhausted and
    the entire API stalled, not just streaming.
    """
    redis = create_worker_redis()
    streams_key = _STREAMS_PREFIX + user_key
    # "$" = only new events. A reconnecting client sends Last-Event-ID and
    # picks up exactly where it stopped, so nothing is dropped in the gap.
    cursor = last_event_id or "$"
    last_auth_check = asyncio.get_event_loop().time()

    try:
        # Tell the browser how long to wait before reconnecting.
        yield "retry: 3000\n\n"

        while True:
            if await request.is_disconnected():
                break

            # Heartbeat this stream's slot under the per-user cap.
            await redis.zadd(streams_key, {stream_id: time.time()})
            await redis.expire(streams_key, _STREAM_STALE_SECONDS)

            now = asyncio.get_event_loop().time()
            if now - last_auth_check > AUTH_RECHECK_SECONDS:
                try:
                    payload = decode_token(raw_token, TOKEN_TYPE_ACCESS)
                    if await is_payload_revoked(payload):
                        raise TokenError("revoked")
                    # A token can outlive its account: disabling a user
                    # used to leave their streams running until expiry.
                    async with _session_factory() as session:
                        if not await _is_active_user(session, payload["sub"]):
                            raise TokenError("user disabled")
                except TokenError:
                    # Tell the client WHY before closing. EventSource can't
                    # see HTTP status codes, so without this a routine 15-min
                    # access-token expiry looked like a network fault: the
                    # client retried with the same expired cookie, got 401s,
                    # and gave up — live updates silently died. On this
                    # event the client refreshes its session, then reconnects.
                    logger.info("SSE closing: token expired or revoked")
                    yield "event: auth-expired\ndata: {}\n\n"
                    break
                last_auth_check = now

            try:
                entries = await redis.xread(
                    {JOBS_STREAM: cursor},
                    count=50,
                    block=SSE_KEEPALIVE_SECONDS * 1000,
                )
            except Exception as exc:
                logger.warning("SSE stream read failed: %s", exc)
                break

            if not entries:
                # SSE comments are invisible to EventSource.onmessage but
                # reset idle timeouts on nginx, CDNs and the browser.
                yield ": ping\n\n"
                continue

            for _stream, messages in entries:
                for message_id, fields in messages:
                    cursor = message_id
                    try:
                        job_data = json.loads(fields["data"])
                    except (ValueError, KeyError):
                        # One malformed entry must not kill the generator for
                        # this client, as an unguarded json.loads used to.
                        logger.warning("Skipping malformed SSE entry %s", message_id)
                        continue

                    if user_skills:
                        # Skill-filtered alerts can only match once skills
                        # exist, i.e. on the `enriched` event. Events from
                        # before `kind` existed carried skills, so they count
                        # as enriched.
                        if job_data.get("kind", KIND_ENRICHED) != KIND_ENRICHED:
                            continue
                        job_skills = {s.lower() for s in (job_data.get("skills") or [])}
                        if not (user_skills & job_skills):
                            continue
                    # The id: field is what makes Last-Event-ID resume work.
                    yield f"id: {message_id}\nevent: job\ndata: {json.dumps(job_data)}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE connection closed by client")
    finally:
        try:
            await redis.zrem(streams_key, stream_id)
        except Exception:
            pass  # the entry goes stale and is pruned on the next connect
        # The old code called unsubscribe() but never closed the connection,
        # leaking one per client. Plain aclose() also left the client's own
        # pool (and its socket) open until garbage collection.
        await redis.aclose(close_connection_pool=True)


@router.get("/jobs/alerts")
async def stream_job_alerts(
    request: Request,
    skills: str = Query("", max_length=2000, description="Comma-separated skills to track"),
    last_event_id: Optional[str] = Query(None, max_length=64, description="Resume cursor from last received event ID"),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    """
    Live job feed.

    Authenticated by the HttpOnly access-token cookie, which the browser
    attaches automatically when EventSource is created with
    `{ withCredentials: true }`.
    """
    payload = _authorize(access_token)
    if await is_payload_revoked(payload):
        raise HTTPException(status_code=401, detail="Token revoked")
    if not await _is_active_user(session, payload["sub"]):
        raise HTTPException(status_code=401, detail="Account unavailable")

    stream_id = uuid.uuid4().hex
    if not await _register_stream(await get_redis_pool(), payload["sub"], stream_id):
        raise HTTPException(status_code=429, detail="Too many open live-update streams")

    parsed_skills = {s.strip().lower() for s in skills.split(",") if s.strip()}
    effective_last_id = sanitize_last_event_id(
        request.headers.get("last-event-id") or last_event_id
    )

    return StreamingResponse(
        job_event_generator(
            request, parsed_skills, access_token, effective_last_id, payload["sub"], stream_id
        ),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
