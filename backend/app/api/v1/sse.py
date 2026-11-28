"""
Server-Sent Events hub for live job-board updates.
"""
import asyncio
import json
import logging
import re
import time
import uuid
from typing import Optional

from fastapi import APIRouter, Cookie, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.auth_cookies import ACCESS_COOKIE
from app.core.database import AsyncSessionLocal
from app.core.events import JOBS_STREAM, KIND_ENRICHED, publish_job_event  # noqa: F401
from app.core.rate_limit import limiter
from app.core.redis import create_sse_redis, get_redis_pool
from app.core.security import TOKEN_TYPE_ACCESS, TokenError, decode_token
from app.core.user_cache import (
    check_revocation_and_get_profile,
    invalidate_user_profile,
    set_cached_user_profile,
)
from app.models.users import User

logger = logging.getLogger(__name__)
router = APIRouter()

SSE_KEEPALIVE_SECONDS = 25
AUTH_RECHECK_SECONDS = 60

MAX_STREAMS_PER_USER = 3
MAX_SSE_SKILLS = 30
_STREAM_STALE_SECONDS = SSE_KEEPALIVE_SECONDS * 3
_STREAMS_PREFIX = "sse:streams:"

_STREAM_ID_RE = re.compile(r"^\d{1,20}-\d{1,20}$")

# Short-lived session factory used for initial cache-miss checks AND periodic
# re-checks so no Postgres connection is ever held open across StreamingResponse.
_session_factory = AsyncSessionLocal


def _authorize(raw_token: Optional[str]) -> dict:
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required")
    try:
        return decode_token(raw_token, TOKEN_TYPE_ACCESS)
    except TokenError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


async def _is_active_user(
    session: AsyncSession, email: str, expected_version: Optional[int] = None
) -> bool:
    user = (
        await session.execute(select(User).where(User.email == email))
    ).scalar_one_or_none()
    if user is None or not user.is_active:
        await invalidate_user_profile(email)
        return False
    if expected_version is not None and user.token_version != expected_version:
        await invalidate_user_profile(email)
        return False
    await set_cached_user_profile(user)
    return True


async def _register_stream(redis, user_key: str, stream_id: str) -> bool:
    """Count this stream against the user's cap; False if over it."""
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
    """Yield SSE frames from the Redis stream, resuming after `last_event_id`."""
    redis = create_sse_redis(SSE_KEEPALIVE_SECONDS)
    streams_key = _STREAMS_PREFIX + user_key
    cursor = last_event_id or "$"
    loop = asyncio.get_running_loop()
    last_auth_check = loop.time()
    last_heartbeat = 0.0

    try:
        yield "retry: 3000\n\n"

        while True:
            if await request.is_disconnected():
                break

            now = loop.time()
            # Throttle heartbeat writes to SSE_KEEPALIVE_SECONDS (pipelined)
            # instead of issuing 2 Redis commands per event burst.
            if now - last_heartbeat >= SSE_KEEPALIVE_SECONDS:
                async with redis.pipeline(transaction=False) as pipe:
                    pipe.zadd(streams_key, {stream_id: time.time()})
                    pipe.expire(streams_key, _STREAM_STALE_SECONDS)
                    await pipe.execute()
                last_heartbeat = now

            if now - last_auth_check > AUTH_RECHECK_SECONDS:
                try:
                    payload = decode_token(raw_token, TOKEN_TYPE_ACCESS)
                    token_ver = payload.get("ver")
                    is_revoked, cached_profile = await check_revocation_and_get_profile(payload)
                    if is_revoked:
                        raise TokenError("revoked")
                    if cached_profile is not None:
                        if not cached_profile.is_active:
                            raise TokenError("user disabled")
                        if token_ver is not None and cached_profile.token_version != token_ver:
                            raise TokenError("token version mismatch")
                    else:
                        async with _session_factory() as session:
                            if not await _is_active_user(session, payload["sub"], token_ver):
                                raise TokenError("user disabled")
                except TokenError:
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
                yield ": ping\n\n"
                continue

            for _stream, messages in entries:
                for message_id, fields in messages:
                    cursor = message_id
                    try:
                        job_data = json.loads(fields["data"])
                    except (ValueError, KeyError):
                        logger.warning("Skipping malformed SSE entry %s", message_id)
                        continue

                    if user_skills:
                        if job_data.get("kind", KIND_ENRICHED) != KIND_ENRICHED:
                            continue
                        job_skills = {s.lower() for s in (job_data.get("skills") or [])}
                        if not (user_skills & job_skills):
                            continue
                    yield f"id: {message_id}\nevent: job\ndata: {json.dumps(job_data)}\n\n"

    except asyncio.CancelledError:
        logger.info("SSE connection closed by client")
    finally:
        try:
            await redis.zrem(streams_key, stream_id)
        except Exception:
            pass
        await redis.aclose(close_connection_pool=True)


@router.get("/jobs/alerts")
@limiter.limit("30/minute")
async def stream_job_alerts(
    request: Request,
    skills: str = Query("", max_length=2000, description="Comma-separated skills to track"),
    last_event_id: Optional[str] = Query(
        None, max_length=64, description="Resume cursor from last received event ID"
    ),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
):
    """
    Live job feed authenticated by the HttpOnly access-token cookie.

    NOTE: Deliberately does NOT inject `Depends(get_session)`: in FastAPI
    >=0.118, yield dependencies stay open until StreamingResponse completes,
    which held a Postgres connection open for the entire lifetime of every
    SSE stream on a profile cache miss.
    """
    payload = _authorize(access_token)
    token_ver = payload.get("ver")
    is_revoked, cached_profile = await check_revocation_and_get_profile(payload)
    if is_revoked:
        raise HTTPException(status_code=401, detail="Token revoked")
    if cached_profile is not None:
        if not cached_profile.is_active:
            raise HTTPException(status_code=401, detail="Account unavailable")
        if token_ver is not None and cached_profile.token_version != token_ver:
            raise HTTPException(status_code=401, detail="Token revoked")
    else:
        async with _session_factory() as session:
            if not await _is_active_user(session, payload["sub"], token_ver):
                raise HTTPException(status_code=401, detail="Account unavailable")

    stream_id = uuid.uuid4().hex
    if not await _register_stream(await get_redis_pool(), payload["sub"], stream_id):
        raise HTTPException(status_code=429, detail="Too many open live-update streams")

    parsed_skills = set(
        [s.strip().lower() for s in skills.split(",") if s.strip()][:MAX_SSE_SKILLS]
    )
    effective_last_id = sanitize_last_event_id(
        request.headers.get("last-event-id") or last_event_id
    )

    return StreamingResponse(
        job_event_generator(
            request, parsed_skills, access_token, effective_last_id, payload["sub"], stream_id
        ),
        media_type="text/event-stream",
        headers={
            "X-Accel-Buffering": "no",
            "Cache-Control": "private, no-cache, no-store",
            "Connection": "keep-alive",
        },
    )
