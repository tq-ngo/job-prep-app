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
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_cookies import ACCESS_COOKIE, is_token_denied
from app.core.database import get_session
from app.core.redis import create_worker_redis
from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token

logger = logging.getLogger(__name__)
router = APIRouter()

SSE_KEEPALIVE_SECONDS = 25
JOBS_STREAM = "jobs:events"
# Bounded so the backlog can't grow without limit. ~10k events is far more
# than any client needs to catch up on after a reconnect.
JOBS_STREAM_MAXLEN = 10_000
# Re-check the token periodically: a connection previously outlived token
# expiry for up to nginx's proxy_read_timeout (24h) because auth was only
# ever validated once, at connect.
AUTH_RECHECK_SECONDS = 60


async def publish_job_event(redis, payload: dict) -> str:
    """Append an event to the stream. Returns its id."""
    return await redis.xadd(
        JOBS_STREAM,
        {"data": json.dumps(payload)},
        maxlen=JOBS_STREAM_MAXLEN,
        approximate=True,
    )


def _authorize(raw_token: Optional[str]) -> dict:
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return decode_token(raw_token, TOKEN_TYPE_ACCESS)
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def job_event_generator(
    request: Request, user_skills: set, raw_token: str, last_event_id: Optional[str]
):
    """
    Yield SSE frames from the Redis stream, resuming after `last_event_id`.

    Uses a dedicated Redis connection rather than the shared API pool: each
    SSE client holds its connection open for the life of the stream, so at
    ~50 concurrent viewers the shared 50-connection pool was exhausted and
    the entire API stalled, not just streaming.
    """
    redis = create_worker_redis()
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

            now = asyncio.get_event_loop().time()
            if now - last_auth_check > AUTH_RECHECK_SECONDS:
                try:
                    payload = decode_token(raw_token, TOKEN_TYPE_ACCESS)
                    if await is_token_denied(payload.get("jti")):
                        raise TokenError("revoked")
                except TokenError:
                    # Close the stream; the client will reconnect and get a
                    # clean 401, which routes it through the logout path.
                    logger.info("SSE closing: token expired or revoked")
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

                    job_skills = {s.lower() for s in (job_data.get("skills") or [])}
                    if user_skills and not (user_skills & job_skills):
                        continue
                    # The id: field is what makes Last-Event-ID resume work.
                    yield f"id: {message_id}\nevent: job\ndata: {json.dumps(job_data)}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE connection closed by client")
    finally:
        # The old code called unsubscribe() but never closed the connection,
        # leaking one per client.
        await redis.aclose()


@router.get("/jobs/alerts")
async def stream_job_alerts(
    request: Request,
    skills: str = Query("", description="Comma-separated skills to track"),
    last_event_id: Optional[str] = Query(None, description="Resume cursor from last received event ID"),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
):
    """
    Live job feed.

    Authenticated by the HttpOnly access-token cookie, which the browser
    attaches automatically when EventSource is created with
    `{ withCredentials: true }`.
    """
    payload = _authorize(access_token)
    if await is_token_denied(payload.get("jti")):
        raise HTTPException(status_code=401, detail="Token revoked")

    parsed_skills = {s.strip().lower() for s in skills.split(",") if s.strip()}
    effective_last_id = request.headers.get("last-event-id") or last_event_id

    return StreamingResponse(
        job_event_generator(request, parsed_skills, access_token, effective_last_id),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",   # disable nginx buffering
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
