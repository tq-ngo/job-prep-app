import pytest
from httpx import AsyncClient

from app.core.auth_cookies import ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE
from app.models.users import User


@pytest.mark.integration
async def test_register_success_and_duplicate_rejection(client: AsyncClient):
    payload = {
        "email": "newuser@example.com",
        "password": "ValidPassword123!",
    }

    # First registration succeeds
    res = await client.post("/api/v1/auth/register", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "newuser@example.com"
    assert "password" not in data

    # Duplicate registration rejected with 400
    res_dup = await client.post("/api/v1/auth/register", json=payload)
    assert res_dup.status_code == 400
    assert "already registered" in res_dup.json()["detail"]


@pytest.mark.integration
async def test_register_password_validation_rejections(client: AsyncClient):
    # Too short
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "Pass1"},
    )
    assert res.status_code == 422

    # No uppercase
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "noupper@example.com", "password": "validpassword123!"},
    )
    assert res.status_code == 422

    # No digits
    res = await client.post(
        "/api/v1/auth/register",
        json={"email": "nodigit@example.com", "password": "ValidPassword!"},
    )
    assert res.status_code == 422

    # Exceeding 72 bytes
    res = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "toolong@example.com",
            "password": "ValidPassword123!" + "A" * 70,
        },
    )
    assert res.status_code == 422


@pytest.mark.integration
async def test_login_success_and_cookie_generation(
    client: AsyncClient, test_user: User
):
    # Valid login using OAuth2 password form
    res = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "ValidPass123!"},
    )
    assert res.status_code == 200

    # Assert HttpOnly and CSRF cookies are set
    cookies = res.cookies
    assert ACCESS_COOKIE in cookies
    assert REFRESH_COOKIE in cookies
    assert CSRF_COOKIE in cookies


@pytest.mark.integration
async def test_login_invalid_credentials_returns_401(
    client: AsyncClient, test_user: User
):
    # Wrong password
    res = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "WrongPassword999!"},
    )
    assert res.status_code == 401
    assert "Incorrect email or password" in res.json()["detail"]

    # Non-existent user
    res_nonexistent = await client.post(
        "/api/v1/auth/login",
        data={"username": "nobody@example.com", "password": "AnyPassword123!"},
    )
    assert res_nonexistent.status_code == 401


@pytest.mark.integration
async def test_get_current_user_me(client: AsyncClient, auth_headers):
    # Authenticated request with cookies
    res = await client.get(
        "/api/v1/auth/me",
        cookies=auth_headers["cookies"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["email"] == "testuser@example.com"

    # Unauthenticated request returns 401
    res_unauth = await client.get("/api/v1/auth/me")
    assert res_unauth.status_code == 401


@pytest.mark.integration
async def test_csrf_protection_on_mutating_requests(client: AsyncClient, auth_headers):
    # Mutating request with auth cookies but WITHOUT CSRF header returns 403
    res_no_csrf = await client.post(
        "/api/v1/auth/logout",
        cookies=auth_headers["cookies"],
    )
    assert res_no_csrf.status_code == 403
    assert "CSRF token missing" in res_no_csrf.json()["detail"]

    # Mutating request with valid CSRF header succeeds
    res_with_csrf = await client.post(
        "/api/v1/auth/logout",
        cookies=auth_headers["cookies"],
        headers=auth_headers["headers"],
    )
    assert res_with_csrf.status_code == 200

