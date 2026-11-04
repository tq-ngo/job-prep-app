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
