"""Refresh rotation, the multi-tab grace window, theft detection and /resume."""
import functools

import pytest
from httpx import AsyncClient

from app.api.v1 import auth as auth_module
from app.core.auth_cookies import ACCESS_COOKIE, CSRF_COOKIE, REFRESH_COOKIE
from app.core.security import TOKEN_TYPE_REFRESH, decode_token


@pytest.fixture(autouse=True)
def fast_rotation_wait(monkeypatch):
    # The real wait polls for up to 3s for a concurrent minter to finish.
    monkeypatch.setattr(
        auth_module,
        "await_rotation_result",
        functools.partial(auth_module.await_rotation_result, timeout=0.05, interval=0.01),
    )


async def _refresh(client: AsyncClient, refresh_token: str, csrf: str = "c"):
    client.cookies.clear()
    return await client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_COOKIE: refresh_token, CSRF_COOKIE: csrf},
        headers={"X-CSRF-Token": csrf},
    )


@pytest.mark.integration
async def test_refresh_rotates_and_grace_window_returns_same_pair(
    client: AsyncClient, auth_headers
):
    old_refresh = auth_headers["cookies"][REFRESH_COOKIE]

    first = await _refresh(client, old_refresh)
    assert first.status_code == 200
    new_refresh = first.cookies[REFRESH_COOKIE]
    assert new_refresh != old_refresh

    # A second tab presenting the same old token within the grace window
    # gets the pair already minted, not a 401.
    second = await _refresh(client, old_refresh)
    assert second.status_code == 200
    assert second.cookies[REFRESH_COOKIE] == new_refresh


@pytest.mark.integration
async def test_reuse_after_grace_revokes_the_family(
    client: AsyncClient, auth_headers, fake_redis
):
    old_refresh = auth_headers["cookies"][REFRESH_COOKIE]
    first = await _refresh(client, old_refresh)
    new_access = first.cookies[ACCESS_COOKIE]

    # Grace window over: the cached rotation result has expired.
    jti = decode_token(old_refresh, TOKEN_TYPE_REFRESH)["jti"]
    await fake_redis.delete(f"jwt:rotated:{jti}")

    replay = await _refresh(client, old_refresh)
    assert replay.status_code == 401

    # Theft response: tokens minted from that sign-in are dead too.
    client.cookies.clear()
    me = await client.get("/api/v1/auth/me", cookies={ACCESS_COOKIE: new_access})
    assert me.status_code == 401


@pytest.mark.integration
async def test_refresh_requires_csrf(client: AsyncClient, auth_headers):
    client.cookies.clear()
    res = await client.post(
        "/api/v1/auth/refresh",
        cookies={REFRESH_COOKIE: auth_headers["cookies"][REFRESH_COOKIE], CSRF_COOKIE: "a"},
        headers={"X-CSRF-Token": "b"},
    )
    assert res.status_code == 403


@pytest.mark.integration
async def test_resume_rotates_and_redirects_to_safe_next(client: AsyncClient, auth_headers):
    client.cookies.clear()
    res = await client.get(
        "/api/v1/auth/resume",
        params={"next": "/news?tab=1"},
        cookies={REFRESH_COOKIE: auth_headers["cookies"][REFRESH_COOKIE]},
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/news?tab=1"
    assert ACCESS_COOKIE in res.cookies


@pytest.mark.integration
async def test_resume_without_session_goes_to_login(client: AsyncClient):
    client.cookies.clear()
    res = await client.get("/api/v1/auth/resume", params={"next": "/jobs"})
    assert res.status_code == 303
    assert res.headers["location"] == "/login?next=/jobs"


@pytest.mark.unit
@pytest.mark.parametrize(
    "candidate",
    ["https://evil.com", "//evil.com", "/\\evil.com", "/jobs\r\nSet-Cookie: x=1", "", None, "jobs"],
)
def test_safe_next_rejects_off_site_targets(candidate):
    assert auth_module._safe_next(candidate) == "/jobs"


@pytest.mark.unit
def test_safe_next_keeps_relative_paths():
    assert auth_module._safe_next("/jobs?jobId=abc") == "/jobs?jobId=abc"


@pytest.mark.integration
async def test_update_skills_normalizes_and_bounds(client: AsyncClient, auth_headers):
    res = await client.put(
        "/api/v1/auth/me/skills",
        json={"skills": ["  Python ", "python", "", "React"]},
        cookies=auth_headers["cookies"],
        headers=auth_headers["headers"],
    )
    assert res.status_code == 200
    assert res.json()["skills"] == ["python", "react"]

    too_many = await client.put(
        "/api/v1/auth/me/skills",
        json={"skills": [f"skill{i}" for i in range(31)]},
        cookies=auth_headers["cookies"],
        headers=auth_headers["headers"],
    )
    assert too_many.status_code == 422

    too_long = await client.put(
        "/api/v1/auth/me/skills",
        json={"skills": ["x" * 41]},
        cookies=auth_headers["cookies"],
        headers=auth_headers["headers"],
    )
    assert too_long.status_code == 422


@pytest.mark.integration
async def test_get_me_uses_redis_profile_cache_without_sql_select(
    client: AsyncClient, auth_headers, test_user, fake_redis, mock_db_session, monkeypatch
):
    from app.core.user_cache import user_profile_key

    key = user_profile_key(test_user.email)
    assert await fake_redis.get(key) is None

    # First call warms Redis from Postgres.
    first = await client.get("/api/v1/auth/me", cookies=auth_headers["cookies"])
    assert first.status_code == 200
    assert await fake_redis.get(key) is not None

    # Second call must serve from Redis without executing any SQL statement.
    exec_calls = 0
    orig_execute = mock_db_session.execute

    async def spy_execute(*args, **kwargs):
        nonlocal exec_calls
        exec_calls += 1
        return await orig_execute(*args, **kwargs)

    monkeypatch.setattr(mock_db_session, "execute", spy_execute)
    second = await client.get("/api/v1/auth/me", cookies=auth_headers["cookies"])
    assert second.status_code == 200
    assert second.json() == {"id": test_user.id, "email": test_user.email, "skills": []}
    assert exec_calls == 0


@pytest.mark.integration
async def test_login_warms_profile_cache_and_logout_evicts_it(
    client: AsyncClient, test_user, fake_redis
):
    from app.core.user_cache import user_profile_key

    key = user_profile_key(test_user.email)
    login_res = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "ValidPass123!"},
    )
    assert login_res.status_code == 200
    assert await fake_redis.get(key) is not None

    logout_res = await client.post(
        "/api/v1/auth/logout",
        cookies=login_res.cookies,
        headers={"X-CSRF-Token": login_res.cookies[CSRF_COOKIE]},
    )
    assert logout_res.status_code == 200
    assert await fake_redis.get(key) is None

    me_after = await client.get(
        "/api/v1/auth/me",
        cookies={ACCESS_COOKIE: login_res.cookies[ACCESS_COOKIE]},
    )
    assert me_after.status_code == 401


@pytest.mark.integration
async def test_update_skills_from_cached_user_updates_db_and_cache(
    client: AsyncClient, auth_headers, test_user, fake_redis, mock_db_session, monkeypatch
):
    import json
    from app.core.user_cache import user_profile_key

    key = user_profile_key(test_user.email)
    # Warm cache first so PUT /me/skills receives a Redis-hydrated transient User.
    warm = await client.get("/api/v1/auth/me", cookies=auth_headers["cookies"])
    assert warm.status_code == 200

    put_res = await client.put(
        "/api/v1/auth/me/skills",
        json={"skills": ["Python", "PostgreSQL"]},
        cookies=auth_headers["cookies"],
        headers=auth_headers["headers"],
    )
    assert put_res.status_code == 200
    assert put_res.json()["skills"] == ["python", "postgresql"]

    cached = json.loads(await fake_redis.get(key))
    assert cached["skills"] == ["python", "postgresql"]

    # Subsequent /me reads updated skills from Redis without SQL.
    exec_calls = 0
    orig_execute = mock_db_session.execute

    async def spy_execute(*args, **kwargs):
        nonlocal exec_calls
        exec_calls += 1
        return await orig_execute(*args, **kwargs)

    monkeypatch.setattr(mock_db_session, "execute", spy_execute)
    me_res = await client.get("/api/v1/auth/me", cookies=auth_headers["cookies"])
    assert me_res.status_code == 200
    assert me_res.json()["skills"] == ["python", "postgresql"]
    assert exec_calls == 0


@pytest.mark.integration
async def test_refresh_evicts_profile_cache_when_user_disabled(
    client: AsyncClient, auth_headers, test_user, fake_redis, mock_db_session
):
    from app.core.user_cache import user_profile_key

    key = user_profile_key(test_user.email)
    assert (await client.get("/api/v1/auth/me", cookies=auth_headers["cookies"])).status_code == 200
    assert await fake_redis.get(key) is not None

    test_user.is_active = False
    mock_db_session.add(test_user)
    await mock_db_session.commit()

    res = await _refresh(client, auth_headers["cookies"][REFRESH_COOKIE])
    assert res.status_code == 401
    assert await fake_redis.get(key) is None
