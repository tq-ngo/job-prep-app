"""
HttpOnly cookie transport + a Redis token denylist.

Tokens previously travelled in the JSON login response and lived in
localStorage, where any XSS could read them, and the SSE endpoint took the
token as a URL query parameter (logged by nginx, kept in browser history and
Referer headers). Cookies marked HttpOnly are unreadable from JavaScript and
are attached automatically by EventSource, which removes both problems.
"""
import asyncio
import json
import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import Response

from app.config import settings
from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)

ACCESS_COOKIE = "access_token"
REFRESH_COOKIE = "refresh_token"
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"

# Refresh cookie is scoped to the refresh/logout endpoints so it is not sent
# on every ordinary API call, limiting its exposure.
REFRESH_COOKIE_PATH = "/api/v1/auth"

_DENYLIST_PREFIX = "jwt:denied:"
_FAMILY_REVOKED_PREFIX = "jwt:family:revoked:"
# Marks a refresh jti as spent; lives for the token's remaining lifetime.
_ROTATION_CLAIM_PREFIX = "jwt:rotating:"
# The pair minted by that rotation, kept briefly for concurrent callers.
_ROTATION_RESULT_PREFIX = "jwt:rotated:"


def _base_kwargs() -> dict:
    kwargs = {
        "httponly": True,
        "secure": settings.COOKIE_SECURE,
        "samesite": settings.COOKIE_SAMESITE,
    }
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    return kwargs


def set_auth_cookies(
    response: Response,
    access_token: str,
    refresh_token: str,
    csrf_token: str,
) -> None:
    """Attach access, refresh and CSRF cookies to a response."""
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        **_base_kwargs(),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path=REFRESH_COOKIE_PATH,
        **_base_kwargs(),
    )
    # Double-submit CSRF token. Deliberately NOT HttpOnly: the frontend has to
    # read it and echo it back in the X-CSRF-Token header. Safe because an
    # attacker on another origin can neither read it nor set the header.
    csrf_kwargs = _base_kwargs()
    csrf_kwargs["httponly"] = False
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600,
        path="/",
        **csrf_kwargs,
    )


def clear_auth_cookies(response: Response) -> None:
    kwargs = {"secure": settings.COOKIE_SECURE, "samesite": settings.COOKIE_SAMESITE}
    if settings.COOKIE_DOMAIN:
        kwargs["domain"] = settings.COOKIE_DOMAIN
    response.delete_cookie(ACCESS_COOKIE, path="/", **kwargs)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, **kwargs)
    response.delete_cookie(CSRF_COOKIE, path="/", **kwargs)


async def deny_token(jti: str, ttl_seconds: int) -> None:
    """
    Revoke a token by jti until it would have expired anyway.

    TTL matches the token's remaining lifetime, so the denylist stays bounded
    instead of growing forever.
    """
    if ttl_seconds <= 0:
        return
    redis = await get_redis_pool()
    await redis.setex(f"{_DENYLIST_PREFIX}{jti}", ttl_seconds, "1")


async def revoke_family(family: str, ttl_seconds: int) -> None:
    """Revoke every token descended from one sign-in."""
    if not family or ttl_seconds <= 0:
        return
    redis = await get_redis_pool()
    await redis.setex(f"{_FAMILY_REVOKED_PREFIX}{family}", ttl_seconds, "1")


async def is_payload_revoked(payload: Dict[str, Any]) -> bool:
    """True if this token's jti, or its whole family, has been revoked."""
    keys = []
    if payload.get("jti"):
        keys.append(f"{_DENYLIST_PREFIX}{payload['jti']}")
    if payload.get("fam"):
        keys.append(f"{_FAMILY_REVOKED_PREFIX}{payload['fam']}")
    if not keys:
        return False
    redis = await get_redis_pool()
    return bool(await redis.exists(*keys))


# ── Refresh rotation with a reuse grace window ───────────────────────────
#
# Rotation used to denylist the presented refresh token immediately. Two tabs
# refreshing at the same moment both sent the same cookie; the second lost
# the race, got 401 "already used", and logged the user out. Now the first
# caller claims the jti and publishes the pair it minted; a caller arriving
# within the grace window receives that same pair. Only a reuse AFTER the
# window is treated as theft.

async def claim_rotation(jti: str, ttl_seconds: int) -> bool:
    """Atomically mark a refresh jti as spent. True for the first caller only."""
    redis = await get_redis_pool()
    return bool(
        await redis.set(f"{_ROTATION_CLAIM_PREFIX}{jti}", "1", nx=True, ex=max(ttl_seconds, 1))
    )


async def store_rotation_result(
    jti: str, tokens: Tuple[str, str, str], grace_seconds: int
) -> None:
    redis = await get_redis_pool()
    await redis.setex(
        f"{_ROTATION_RESULT_PREFIX}{jti}", grace_seconds, json.dumps(list(tokens))
    )


async def await_rotation_result(
    jti: str, timeout: float = 3.0, interval: float = 0.1
) -> Optional[Tuple[str, str, str]]:
    """
    Fetch the pair minted for an already-claimed jti.

    Polls briefly because a concurrent caller may have claimed the jti but
    not yet finished minting. None means the grace window has passed.
    """
    redis = await get_redis_pool()
    key = f"{_ROTATION_RESULT_PREFIX}{jti}"
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        raw = await redis.get(key)
        if raw is not None:
            access, refresh, csrf = json.loads(raw)
            return access, refresh, csrf
        if asyncio.get_running_loop().time() >= deadline:
            return None
        await asyncio.sleep(interval)
