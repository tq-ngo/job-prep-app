import json
import logging
import asyncio
from fastapi import APIRouter, Request, Query
from fastapi.responses import StreamingResponse

from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)
router = APIRouter()

SSE_KEEPALIVE_SECONDS = 25

async def job_event_generator(request: Request, user_skills: set):
    """
    Async generator that subscribes to Redis PubSub and yields SSE strings.
    Emits a keepalive comment every 25s to prevent proxy/browser timeouts.
    """
    redis = await get_redis_pool()
    pubsub = redis.pubsub()
    await pubsub.subscribe("new_jobs_channel")
    
    logger.info(f"SSE Client connected tracking skills: {user_skills}")
    
    try:
        while True:
            # Stop generator if client disconnects
            if await request.is_disconnected():
                break

            try:
                # Use wait_for with a 25s timeout on each listen iteration.
                # If no message arrives within 25s, asyncio.TimeoutError is raised
                # and we emit a keepalive comment to reset proxy/browser timeouts.
                message = await asyncio.wait_for(
                    pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0),
                    timeout=SSE_KEEPALIVE_SECONDS,
                )
            except asyncio.TimeoutError:
                # No job message in 25s — emit a keepalive comment.
                # SSE comments (lines starting with ':') are transparent to
                # EventSource.onmessage but they reset idle timeouts on all
                # intermediaries (Nginx, CDNs, browser TCP keepalive).
                yield ": ping\n\n"
                continue

            if message and message.get("type") == "message":
                job_data = json.loads(message["data"])
                job_skills = {s.lower() for s in (job_data.get("skills") or [])}
                
                # Push event if client has no specific filters OR if skills overlap
                if not user_skills or (user_skills & job_skills):
                    yield f"data: {json.dumps(job_data)}\n\n"
                    
    except asyncio.CancelledError:
        logger.info("SSE connection closed by client")
    finally:
        await pubsub.unsubscribe("new_jobs_channel")

@router.get("/jobs/alerts")
async def stream_job_alerts(
    request: Request, 
    skills: str = Query("", description="Comma-separated skills to track")
):
    """
    Server-Sent Events endpoint for real-time job board updates.
    """
    parsed_skills = {s.strip().lower() for s in skills.split(",") if s.strip()}
    return StreamingResponse(
        job_event_generator(request, parsed_skills),
        media_type="text/event-stream",
        headers={
            # Disable buffering on Nginx and other reverse proxies
            "X-Accel-Buffering": "no",
            "Cache-Control": "no-cache",
        },
    )
