from urllib.parse import parse_qs, urlparse

import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.config import settings
from app.core.google_oauth import BINDING_COOKIE
from app.models.users import User


@pytest.fixture(autouse=True)
def google_configured(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "client-id")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "client-secret")


@pytest.fixture
def google_returns(monkeypatch):
    """Stub the token exchange and id_token check with fixed claims."""
    claims = {}

    async def fake_exchange(code, verifier):
        return {"id_token": "signed-by-google"}

    def fake_verify(raw, nonce):
        return dict(claims)

    monkeypatch.setattr("app.api.v1.auth.exchange_code", fake_exchange)
    monkeypatch.setattr("app.api.v1.auth.verify_id_token", fake_verify)
    return claims


async def _start_flow(client: AsyncClient) -> str:
    res = await client.get("/api/v1/auth/google/login", params={"next": "/news"})
    assert res.status_code == 307
    assert BINDING_COOKIE in res.cookies
    return parse_qs(urlparse(res.headers["location"]).query)["state"][0]


@pytest.mark.integration
async def test_new_google_user_is_created_and_signed_in(
    client: AsyncClient, google_returns, mock_db_session
):
    google_returns.update(email="New.Person@Gmail.com", sub="g-123", name="New Person")
    state = await _start_flow(client)

    res = await client.get("/api/v1/auth/google/callback", params={"state": state, "code": "c"})

    assert res.status_code == 303
    assert res.headers["location"].endswith("/news")
    assert "access_token" in res.cookies
    user = (
        await mock_db_session.execute(select(User).where(User.google_sub == "g-123"))
    ).scalar_one()
    assert user.email == "new.person@gmail.com"


@pytest.mark.integration
async def test_google_does_not_auto_link_to_password_account(
    client: AsyncClient, google_returns, test_user, mock_db_session
):
    # Someone registered this address with a password; Google proving the
    # victim owns it must not hand the victim's sign-in to that account.
    google_returns.update(email=test_user.email.upper(), sub="g-victim")
    state = await _start_flow(client)

    res = await client.get("/api/v1/auth/google/callback", params={"state": state, "code": "c"})

    assert res.status_code == 303
    assert res.headers["location"].endswith("/login?error=account_exists")
    assert "access_token" not in res.cookies
    await mock_db_session.refresh(test_user)
    assert test_user.google_sub is None


@pytest.mark.integration
async def test_callback_from_another_browser_is_rejected(
    client: AsyncClient, google_returns
):
    google_returns.update(email="someone@gmail.com", sub="g-9")
    state = await _start_flow(client)

    # The victim's browser: it holds the callback URL but not the binding
    # cookie set on the attacker's browser.
    client.cookies.clear()
    res = await client.get("/api/v1/auth/google/callback", params={"state": state, "code": "c"})
    assert res.headers["location"].endswith("/login?error=oauth_failed")
    assert "access_token" not in res.cookies

    # And the state was consumed, so the real browser can't reuse it either.
    client.cookies.set(BINDING_COOKIE, "forged-value")
    res = await client.get("/api/v1/auth/google/callback", params={"state": state, "code": "c"})
    assert res.headers["location"].endswith("/login?error=oauth_failed")


@pytest.mark.integration
async def test_disabled_google_user_is_refused_before_any_write(
    client: AsyncClient, google_returns, mock_db_session
):
    user = User(email="gone@gmail.com", google_sub="g-off", is_active=False, avatar_url=None)
    mock_db_session.add(user)
    await mock_db_session.commit()

    google_returns.update(email="gone@gmail.com", sub="g-off", picture="https://new/avatar")
    state = await _start_flow(client)
    res = await client.get("/api/v1/auth/google/callback", params={"state": state, "code": "c"})

    assert res.headers["location"].endswith("/login?error=account_disabled")
    await mock_db_session.refresh(user)
    assert user.avatar_url is None
