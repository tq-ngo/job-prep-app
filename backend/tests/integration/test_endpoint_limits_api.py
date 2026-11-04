from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient

from app.ai.gemini_client import GeminiTransientError
from app.config import settings


@pytest.fixture
def gemini_key(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")


# ── Semantic search ─────────────────────────────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize(
    "params",
    [
        {"query_text": "x" * 201},
        {"query_text": "x"},
        {"query_text": "react", "page": 21},
    ],
)
async def test_search_rejects_out_of_bounds_params(client: AsyncClient, auth_headers, params):
    res = await client.get("/api/v1/search/semantic", params=params, cookies=auth_headers["cookies"])
    assert res.status_code == 422


@pytest.mark.integration
async def test_search_hides_embedding_errors(client: AsyncClient, auth_headers, gemini_key):
    with patch(
        "app.api.v1.search.generate_embedding",
        new=AsyncMock(side_effect=RuntimeError("API key AIza-secret invalid")),
    ):
        res = await client.get(
            "/api/v1/search/semantic", params={"query_text": "react"}, cookies=auth_headers["cookies"]
        )
    assert res.status_code == 503
    assert "AIza" not in res.text


@pytest.mark.integration
async def test_search_passes_through_retry_after(client: AsyncClient, auth_headers, gemini_key):
    with patch(
        "app.api.v1.search.generate_embedding",
        new=AsyncMock(side_effect=GeminiTransientError("429", retry_after=26)),
    ):
        res = await client.get(
            "/api/v1/search/semantic", params={"query_text": "react"}, cookies=auth_headers["cookies"]
        )
    assert res.status_code == 503
    assert res.headers["retry-after"] == "26"


@pytest.mark.unit
async def test_query_embeddings_are_cached(gemini_key):
    from app.api.v1.search import _query_embedding

    embed = AsyncMock(return_value=[0.1, 0.2])
    with patch("app.api.v1.search.generate_embedding", new=embed):
        first = await _query_embedding("React  Frontend")
        second = await _query_embedding("react frontend")  # same after normalizing

    assert first == second == [0.1, 0.2]
    embed.assert_awaited_once_with("react frontend", task_type="RETRIEVAL_QUERY")


# ── SSE ─────────────────────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1730000000000-0", "1730000000000-0"),
        ("garbage", None),
        ("$", None),
        ("1-2-3", None),
        ("", None),
        (None, None),
    ],
)
def test_sse_last_event_id_is_sanitized(raw, expected):
    from app.api.v1.sse import sanitize_last_event_id

    assert sanitize_last_event_id(raw) == expected


@pytest.mark.unit
async def test_sse_caps_streams_per_user(fake_redis):
    from app.api.v1.sse import MAX_STREAMS_PER_USER, _register_stream

    for i in range(MAX_STREAMS_PER_USER):
        assert await _register_stream(fake_redis, "u@example.com", f"s{i}")
    assert not await _register_stream(fake_redis, "u@example.com", "one-too-many")
    # The refused stream doesn't hold a slot, and other users are unaffected.
    assert await fake_redis.zcard("sse:streams:u@example.com") == MAX_STREAMS_PER_USER
    assert await _register_stream(fake_redis, "other@example.com", "s0")


@pytest.mark.unit
async def test_sse_stale_streams_free_their_slots(fake_redis):
    from app.api.v1.sse import MAX_STREAMS_PER_USER, _register_stream

    key = "sse:streams:u@example.com"
    # Streams whose process died without cleanup: heartbeats from 1970.
    await fake_redis.zadd(key, {f"dead{i}": 1.0 for i in range(MAX_STREAMS_PER_USER)})
    assert await _register_stream(fake_redis, "u@example.com", "fresh")


@pytest.mark.integration
async def test_sse_refuses_disabled_user(client: AsyncClient, auth_headers, test_user, mock_db_session):
    test_user.is_active = False
    mock_db_session.add(test_user)
    await mock_db_session.commit()

    res = await client.get("/api/v1/stream/jobs/alerts", cookies=auth_headers["cookies"])
    assert res.status_code == 401


# ── CSRF on state-changing scrape routes ────────────────────────────────

@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    ["/api/v1/jobs/scrape/github", "/api/v1/news/scrape?url=https://example.com", "/api/v1/news/scrape/linkedin"],
)
async def test_scrape_routes_require_csrf(client: AsyncClient, auth_headers, path):
    res = await client.post(path, cookies=auth_headers["cookies"])  # no X-CSRF-Token
    assert res.status_code == 403


# ── JobCreate.apply_url ─────────────────────────────────────────────────

@pytest.mark.unit
@pytest.mark.parametrize("url", ["javascript:alert(1)", "data:text/html,x", "ftp://x/y", "//evil.com"])
def test_apply_url_rejects_non_http_schemes(url):
    from pydantic import ValidationError

    from app.schemas.job import JobCreate

    with pytest.raises(ValidationError):
        JobCreate(
            external_id="1", source="github", title="SWE Intern", company="Acme", apply_url=url
        )


# ── Settings ────────────────────────────────────────────────────────────

def _settings(**overrides):
    from app.config import Settings

    base = dict(
        DATABASE_URL="postgresql+asyncpg://x/y",
        REDIS_URL="redis://x",
        CELERY_BROKER_URL="redis://x",
        CELERY_RESULT_BACKEND="redis://x",
        SECRET_KEY="k" * 40,
    )
    return Settings(_env_file=None, **{**base, **overrides})


@pytest.mark.unit
def test_settings_reject_wildcard_cors():
    with pytest.raises(ValueError, match="CORS_ORIGINS"):
        _settings(CORS_ORIGINS="http://localhost,*")


@pytest.mark.unit
def test_settings_validate_samesite():
    assert _settings(COOKIE_SAMESITE="Strict").COOKIE_SAMESITE == "strict"
    with pytest.raises(ValueError, match="COOKIE_SAMESITE must be one of"):
        _settings(COOKIE_SAMESITE="sometimes")
    with pytest.raises(ValueError, match="requires COOKIE_SECURE"):
        _settings(COOKIE_SAMESITE="none", COOKIE_SECURE=False)


@pytest.mark.unit
def test_docs_disabled_in_production(monkeypatch):
    from app import main

    monkeypatch.setattr(settings, "APP_ENV", "production")
    prod_app = main.create_app()
    assert prod_app.docs_url is None
    assert prod_app.redoc_url is None
    assert prod_app.openapi_url is None
