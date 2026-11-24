"""
Redis cache-aside store for verified user profiles (`user:profile:{email}`).

Replaces the per-request PostgreSQL `SELECT` in `get_current_user` (and SSE's
periodic active-user re-check) with a single pipelined Redis round-trip alongside
JWT revocation checks. Sensitive credential columns (`hashed_password`,
`google_sub`) are never cached.
"""
import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, ValidationError

from app.config import settings
from app.core.auth_cookies import revocation_keys
from app.core.redis import get_redis_pool
from app.models.users import User

logger = logging.getLogger(__name__)

USER_PROFILE_PREFIX = "user:profile:"


class CachedUserProfile(BaseModel):
    """Non-sensitive subset of User stored in Redis."""

    id: int
    email: str
    skills: List[str] = []
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: bool = True


def user_profile_key(email: str) -> str:
    """Return the Redis cache key for a user's email."""
    return f"{USER_PROFILE_PREFIX}{email}"


def to_user_model(profile: CachedUserProfile) -> User:
    """Reconstruct a transient User ORM object from a cached profile."""
    return User(
        id=profile.id,
        email=profile.email,
        skills=list(profile.skills),
        full_name=profile.full_name,
        avatar_url=profile.avatar_url,
        is_active=profile.is_active,
    )


def _from_user_model(user: User) -> CachedUserProfile:
    return CachedUserProfile(
        id=user.id,
        email=user.email,
        skills=list(user.skills or []),
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        is_active=user.is_active,
    )


def _parse_profile(raw: str) -> Optional[CachedUserProfile]:
    try:
        return CachedUserProfile.model_validate_json(raw)
    except (ValueError, ValidationError) as exc:
        logger.warning("Invalid cached user profile payload; evicting: %s", exc)
        return None


async def _resolve_redis(redis: Optional[Any]):
    return redis if redis is not None else await get_redis_pool()


async def get_cached_user_profile(
    email: str, redis: Optional[Any] = None
) -> Optional[CachedUserProfile]:
    """Fetch and validate a cached user profile, or return None on miss/corrupt entry."""
    if settings.USER_PROFILE_CACHE_TTL_SECONDS <= 0 or not email:
        return None
    client = await _resolve_redis(redis)
    key = user_profile_key(email)
    raw = await client.get(key)
    if raw is None:
        return None
    profile = _parse_profile(raw)
    if profile is None:
        await client.delete(key)
    return profile


async def set_cached_user_profile(user: User, redis: Optional[Any] = None) -> None:
    """Write-through cache update for an active, persisted User."""
    ttl = settings.USER_PROFILE_CACHE_TTL_SECONDS
    if ttl <= 0 or user.id is None or not user.is_active:
        return
    client = await _resolve_redis(redis)
    payload = _from_user_model(user).model_dump_json()
    await client.setex(user_profile_key(user.email), ttl, payload)


async def invalidate_user_profile(email: str, redis: Optional[Any] = None) -> None:
    """Evict a cached user profile from Redis."""
    if not email:
        return
    client = await _resolve_redis(redis)
    await client.delete(user_profile_key(email))


async def check_revocation_and_get_profile(
    payload: Dict[str, Any], redis: Optional[Any] = None
) -> Tuple[bool, Optional[CachedUserProfile]]:
    """
    Check JWT revocation and fetch `user:profile:{sub}` in one Redis round-trip.

    Returns `(is_revoked, cached_profile)`. If the token is revoked, returns
    `(True, None)` without parsing the profile.
    """
    rev_keys = revocation_keys(payload)
    email = payload.get("sub") or ""
    cache_enabled = settings.USER_PROFILE_CACHE_TTL_SECONDS > 0 and bool(email)

    if not rev_keys and not cache_enabled:
        return False, None

    client = await _resolve_redis(redis)
    profile_key = user_profile_key(email) if cache_enabled else ""

    if rev_keys and cache_enabled:
        async with client.pipeline(transaction=False) as pipe:
            pipe.exists(*rev_keys)
            pipe.get(profile_key)
            exists_res, raw = await pipe.execute()
        is_revoked = bool(exists_res)
    elif rev_keys:
        is_revoked = bool(await client.exists(*rev_keys))
        raw = None
    else:
        is_revoked = False
        raw = await client.get(profile_key)

    if is_revoked:
        return True, None
    if raw is None:
        return False, None

    profile = _parse_profile(raw)
    if profile is None:
        await client.delete(profile_key)
    return False, profile
