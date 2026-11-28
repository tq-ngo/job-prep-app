import json

import pytest

from app.config import settings
from app.core.auth_cookies import deny_token, revoke_family
from app.core.user_cache import (
    check_revocation_and_get_profile,
    get_cached_user_profile,
    invalidate_user_profile,
    set_cached_user_profile,
    to_user_model,
    user_profile_key,
)
from app.models.users import User


def _sample_user(**overrides) -> User:
    defaults = dict(
        id=42,
        email="alice@example.com",
        hashed_password="$2b$12$secret-hash-should-not-be-cached",
        google_sub="google-sub-secret",
        full_name="Alice",
        avatar_url="https://example.com/a.png",
        skills=["python", "fastapi"],
        is_active=True,
    )
    defaults.update(overrides)
    return User(**defaults)


@pytest.mark.unit
async def test_set_and_get_user_profile_excludes_sensitive_fields(fake_redis):
    user = _sample_user()
    await set_cached_user_profile(user)

    key = user_profile_key(user.email)
    assert key == "user:profile:alice@example.com"

    raw = await fake_redis.get(key)
    assert raw is not None
    data = json.loads(raw)
    assert data == {
        "id": 42,
        "email": "alice@example.com",
        "skills": ["python", "fastapi"],
        "full_name": "Alice",
        "avatar_url": "https://example.com/a.png",
        "is_active": True,
        "is_admin": False,
        "token_version": 1,
    }
    assert "hashed_password" not in raw
    assert "google_sub" not in raw
    ttl = await fake_redis.ttl(key)
    assert 0 < ttl <= settings.USER_PROFILE_CACHE_TTL_SECONDS

    cached = await get_cached_user_profile(user.email)
    assert cached is not None
    hydrated = to_user_model(cached)
    assert hydrated.id == 42
    assert hydrated.email == "alice@example.com"
    assert hydrated.skills == ["python", "fastapi"]
    assert hydrated.is_active is True


@pytest.mark.unit
async def test_set_skips_inactive_or_unpersisted_and_respects_zero_ttl(
    fake_redis, monkeypatch
):
    await set_cached_user_profile(_sample_user(is_active=False))
    assert await fake_redis.get(user_profile_key("alice@example.com")) is None

    await set_cached_user_profile(_sample_user(id=None))
    assert await fake_redis.get(user_profile_key("alice@example.com")) is None

    monkeypatch.setattr(settings, "USER_PROFILE_CACHE_TTL_SECONDS", 0)
    await set_cached_user_profile(_sample_user())
    assert await fake_redis.get(user_profile_key("alice@example.com")) is None
    assert await get_cached_user_profile("alice@example.com") is None


@pytest.mark.unit
async def test_check_revocation_and_get_profile_pipeline(fake_redis):
    user = _sample_user()
    await set_cached_user_profile(user)
    payload = {"sub": user.email, "jti": "jti-1", "fam": "fam-1"}

    is_revoked, profile = await check_revocation_and_get_profile(payload)
    assert is_revoked is False
    assert profile is not None
    assert profile.id == 42

    # Revoking the token jti blocks access even with a warm profile cache.
    await deny_token("jti-1", 60)
    is_revoked, profile = await check_revocation_and_get_profile(payload)
    assert is_revoked is True
    assert profile is None

    # Revoking the token family also blocks a fresh jti.
    await revoke_family("fam-1", 60)
    is_revoked, profile = await check_revocation_and_get_profile(
        {"sub": user.email, "jti": "jti-2", "fam": "fam-1"}
    )
    assert is_revoked is True
    assert profile is None


@pytest.mark.unit
async def test_corrupt_profile_entry_is_evicted_gracefully(fake_redis):
    key = user_profile_key("alice@example.com")
    await fake_redis.set(key, "{not-valid-json")

    is_revoked, profile = await check_revocation_and_get_profile(
        {"sub": "alice@example.com", "jti": "jti-1", "fam": "fam-1"}
    )
    assert is_revoked is False
    assert profile is None
    assert await fake_redis.get(key) is None


@pytest.mark.unit
async def test_invalidate_user_profile_removes_key(fake_redis):
    await set_cached_user_profile(_sample_user())
    key = user_profile_key("alice@example.com")
    assert await fake_redis.get(key) is not None

    await invalidate_user_profile("alice@example.com")
    assert await fake_redis.get(key) is None
