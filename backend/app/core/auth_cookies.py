"""
HttpOnly cookie transport + a Redis token denylist.

Tokens previously travelled in the JSON login response and lived in
localStorage, where any XSS could read them, and the SSE endpoint took the
token as a URL query parameter (logged by nginx, kept in browser history and
Referer headers). Cookies marked HttpOnly are unreadable from JavaScript and
are attached automatically by EventSource, which removes both problems.
"""
import logging
from typing import Optional

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


async def is_token_denied(jti: Optional[str]) -> bool:
    if not jti:
        return False
    redis = await get_redis_pool()
    return bool(await redis.exists(f"{_DENYLIST_PREFIX}{jti}"))
