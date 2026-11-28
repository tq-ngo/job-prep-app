"""Regression tests for Phase 1-3 audit remediations."""
import inspect
import ipaddress
import math
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from google.genai import types
from httpx import AsyncClient
from redis.exceptions import RedisError

from app.ai.embedder import generate_embedding
from app.ai.gemini_client import (
    GeminiConfigError,
    GeminiTransientError,
    _build_thinking_config,
    verify_model,
)
from app.ai.skill_extractor import JobAttributes
from app.config import Settings, settings
from app.core.google_oauth import OAuthError, exchange_code
from app.core.security import create_access_token, new_token_family
from app.core.task_owner import record_task_owner
from app.core.url_guard import UnsafeUrlError, resolve_crawl_target
from app.scraping.db_sync import (
    JOBS_COUNT_VERSION_KEY,
    DatabaseSyncService,
    invalidate_jobs_count_cache,
)
from app.scraping.http_scraper import TLSImpersonateScraper
from app.scraping.jd_extractor import _host_matches, enrich_with_descriptions
from app.scraping.news_parser import _parse_iso_datetime
from app.scraping.parsers.github import _parse_markdown_tables, parse_relative_date
from app.scraping.sponsorship import classify_sponsorship


# ── Phase 1: Embeddings, ThinkingConfig & Redis resilience ───────────────

@pytest.mark.unit
def test_default_embedding_model_is_supported():
    s = Settings(
        _env_file=None,
        DATABASE_URL="postgresql+asyncpg://x/y",
        REDIS_URL="redis://x",
        CELERY_BROKER_URL="redis://x",
        CELERY_RESULT_BACKEND="redis://x",
        SECRET_KEY="a" * 32,
    )
    assert s.EMBEDDING_MODEL == "gemini-embedding-001"
    assert s.EMBEDDING_DIMENSIONS == 768


@pytest.mark.unit
async def test_generate_embedding_sets_output_dimensionality_and_normalizes(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_DIMENSIONS", 4)
    fake_client = MagicMock()
    fake_client.aio.models.embed_content = AsyncMock(
        return_value=SimpleNamespace(embeddings=[SimpleNamespace(values=[3.0, 4.0, 0.0, 0.0])])
    )
    with patch("app.ai.embedder._get_client", return_value=fake_client):
        vec = await generate_embedding("hello world", task_type="RETRIEVAL_QUERY")

    call_kwargs = fake_client.aio.models.embed_content.call_args.kwargs
    assert call_kwargs["config"].output_dimensionality == 4
    assert call_kwargs["config"].task_type == "RETRIEVAL_QUERY"
    assert math.isclose(math.sqrt(sum(v * v for v in vec)), 1.0, rel_tol=1e-6)
    assert vec[0] == pytest.approx(0.6)
    assert vec[1] == pytest.approx(0.8)


@pytest.mark.unit
def test_thinking_config_adapts_to_gemini_3_vs_2_5(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-3.8-flash")
    cfg3 = _build_thinking_config(0)
    assert cfg3.thinking_level == types.ThinkingLevel.LOW
    assert cfg3.thinking_budget is None

    monkeypatch.setattr(settings, "GEMINI_MODEL", "gemini-2.5-flash")
    cfg25 = _build_thinking_config(0)
    assert cfg25.thinking_budget == 0


@pytest.mark.unit
async def test_verify_model_checks_both_models_and_tolerates_transient(monkeypatch):
    monkeypatch.setattr(settings, "GEMINI_API_KEY", "test-key")
    fake_client = MagicMock()
    fake_client.aio.models.get = AsyncMock(side_effect=[None, RuntimeError("404 not found")])
    with patch("app.ai.gemini_client._get_client", return_value=fake_client):
        with pytest.raises(GeminiConfigError, match="EMBEDDING_MODEL"):
            await verify_model()

    fake_client.aio.models.get = AsyncMock(side_effect=RuntimeError("503 Service Unavailable"))
    with patch("app.ai.gemini_client._get_client", return_value=fake_client):
        await verify_model()  # transient error warns without crashing boot


@pytest.mark.integration
async def test_semantic_search_rejects_whitespace_only_query(client: AsyncClient, auth_headers):
    res = await client.get(
        "/api/v1/search/semantic",
        params={"query_text": "    "},
        cookies=auth_headers["cookies"],
    )
    assert res.status_code == 422


@pytest.mark.integration
async def test_stats_degrades_gracefully_on_cache_redis_error(client: AsyncClient, monkeypatch):
    broken = MagicMock()
    broken.get = AsyncMock(side_effect=RedisError("redis down"))
    broken.set = AsyncMock(side_effect=RedisError("redis down"))
    monkeypatch.setattr("app.api.v1.stats.get_cache_redis", AsyncMock(return_value=broken))

    res = await client.get("/api/v1/stats/")
    assert res.status_code == 200
    assert res.headers["cache-control"] == "public, max-age=60"
    assert "active_jobs" in res.json()


# ── Phase 2: Auth, BFLA, SSE pool, rate limits, tasks ────────────────────

@pytest.mark.unit
def test_sse_endpoint_does_not_hold_depends_get_session():
    from app.api.v1.sse import stream_job_alerts

    sig = inspect.signature(stream_job_alerts)
    assert "session" not in sig.parameters


@pytest.mark.unit
def test_settings_reject_placeholder_secret_off_dev():
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            APP_ENV="staging",
            COOKIE_SECURE=True,
            DATABASE_URL="postgresql+asyncpg://x/y",
            REDIS_URL="redis://x",
            CELERY_BROKER_URL="redis://x",
            CELERY_RESULT_BACKEND="redis://x",
            SECRET_KEY="CHANGE_ME_generate_a_random_secret_key",
        )


@pytest.mark.unit
@pytest.mark.parametrize("role", ["worker", "migrate"])
def test_settings_allow_worker_and_migrate_without_secret_key(monkeypatch, role):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    s = Settings(
        _env_file=None,
        SERVICE_ROLE=role,
        APP_ENV="production",
        DATABASE_URL="postgresql+asyncpg://x/y",
        REDIS_URL="redis://x",
        CELERY_BROKER_URL="redis://x",
        CELERY_RESULT_BACKEND="redis://x",
    )
    assert s.SERVICE_ROLE == role
    assert s.SECRET_KEY == ""


@pytest.mark.unit
def test_settings_require_secret_key_for_api_role(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)
    with pytest.raises(ValueError, match="SECRET_KEY"):
        Settings(
            _env_file=None,
            SERVICE_ROLE="api",
            APP_ENV="development",
            DATABASE_URL="postgresql+asyncpg://x/y",
            REDIS_URL="redis://x",
            CELERY_BROKER_URL="redis://x",
            CELERY_RESULT_BACKEND="redis://x",
        )


@pytest.mark.integration
@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/jobs/scrape/github",
        "/api/v1/news/scrape?url=https://example.com/post",
        "/api/v1/news/scrape/linkedin",
    ],
)
async def test_non_admin_cannot_trigger_scrapes(client: AsyncClient, auth_headers, path):
    res = await client.post(
        path, cookies=auth_headers["cookies"], headers=auth_headers["headers"]
    )
    assert res.status_code == 403


@pytest.mark.integration
async def test_jobs_min_salary_rejects_int32_overflow(client: AsyncClient, auth_headers):
    res = await client.get(
        "/api/v1/jobs/",
        params={"min_salary": 3_000_000_000},
        cookies=auth_headers["cookies"],
    )
    assert res.status_code == 422


@pytest.mark.integration
async def test_bearer_logout_revokes_token(client: AsyncClient, test_user):
    token, _, _ = create_access_token(test_user.email, new_token_family())
    headers = {"Authorization": f"Bearer {token}"}

    before = await client.get("/api/v1/auth/me", headers=headers)
    assert before.status_code == 200

    out = await client.post("/api/v1/auth/logout", headers=headers)
    assert out.status_code == 200

    after = await client.get("/api/v1/auth/me", headers=headers)
    assert after.status_code == 401


@pytest.mark.integration
async def test_resume_rejects_cross_site_navigation(client: AsyncClient, auth_headers):
    res = await client.get(
        "/api/v1/auth/resume",
        params={"next": "/jobs"},
        cookies={"refresh_token": auth_headers["cookies"]["refresh_token"]},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert res.status_code == 303
    assert res.headers["location"] == "/login?next=/jobs"
    assert "access_token" not in res.cookies


@pytest.mark.integration
async def test_login_rejects_cross_site_post(client: AsyncClient, test_user):
    res = await client.post(
        "/api/v1/auth/login",
        data={"username": test_user.email, "password": "ValidPass123!"},
        headers={"Sec-Fetch-Site": "cross-site"},
    )
    assert res.status_code == 403


@pytest.mark.unit
async def test_oauth_exchange_wraps_httpx_errors():
    with patch(
        "app.core.google_oauth.httpx.AsyncClient.post",
        new=AsyncMock(side_effect=httpx.ConnectTimeout("timeout")),
    ):
        with pytest.raises(OAuthError, match="network error"):
            await exchange_code("code", "verifier")


@pytest.mark.integration
async def test_tasks_empty_ids_422_and_sanitized_failure(
    client: AsyncClient, auth_headers, test_user
):
    empty = await client.get("/api/v1/tasks/,,,", cookies=auth_headers["cookies"])
    assert empty.status_code == 422

    await record_task_owner(["fail-1", "ok-1"], test_user.id)

    def _mock_res(tid):
        m = MagicMock()
        if tid == "fail-1":
            m.state = "FAILURE"
            m.info = RuntimeError("postgresql://secret:pw@db/prod")
            m.result = None
        else:
            m.state = "SUCCESS"
            m.info = None
            m.result = {"ok": True}
        return m

    with patch("app.tasks.celery_app.celery_app.AsyncResult", side_effect=_mock_res):
        single = await client.get("/api/v1/tasks/fail-1", cookies=auth_headers["cookies"])
        assert single.status_code == 200
        assert single.json()["error"] == "Task execution failed"
        assert "secret:pw" not in single.text

        batch = await client.get("/api/v1/tasks/fail-1,ok-1", cookies=auth_headers["cookies"])
        assert batch.status_code == 200
        assert batch.json()["status"] == "PARTIAL_FAILURE"


# ── Phase 3: Scraping, Dedup, AI safety & DB helpers ─────────────────────

@pytest.mark.unit
async def test_enrich_with_descriptions_preserves_linkedin_external_id():
    records = [
        {
            "apply_url": "https://www.linkedin.com/jobs/view/swe-intern-1234567890",
            "source": "linkedin",
            "external_id": "1234567890",
            "description": None,
        }
    ]
    seen_args = []

    async def _fake_fetch(apply_url, source, external_id):
        seen_args.append((apply_url, source, external_id))
        return "## LinkedIn JD", "linkedin"

    with patch("app.scraping.jd_extractor.fetch_jd_with_source", side_effect=_fake_fetch):
        filled = await enrich_with_descriptions(records)

    assert filled == 1
    assert seen_args == [
        ("https://www.linkedin.com/jobs/view/swe-intern-1234567890", "linkedin", "1234567890")
    ]


@pytest.mark.unit
def test_ats_host_matching_enforces_dot_boundary():
    assert _host_matches("boards.greenhouse.io", "greenhouse.io")
    assert not _host_matches("greenhouse.io.attacker.com", "greenhouse.io")


@pytest.mark.unit
def test_url_guard_rejects_non_web_ports():
    public = ipaddress.ip_address("93.184.216.34")
    with patch("app.core.url_guard._resolve", return_value=[public]):
        assert resolve_crawl_target("https://example.com/a").port == 443
        with pytest.raises(UnsafeUrlError, match="not allowed"):
            resolve_crawl_target("http://example.com:6379/")


@pytest.mark.unit
async def test_http_scraper_strips_cookie_on_cross_host_redirect():
    public = ipaddress.ip_address("93.184.216.34")
    r1 = MagicMock(status_code=302, text="", headers={"location": "https://other.org/next"})
    r2 = MagicMock(status_code=200, text="ok", headers={})
    cb = MagicMock(
        allow_request=AsyncMock(return_value=True),
        record_success=AsyncMock(),
        record_failure=AsyncMock(),
    )
    with patch("app.core.url_guard._resolve", return_value=[public]), patch(
        "app.scraping.http_scraper.circuit_breaker", cb
    ), patch("app.scraping.http_scraper.requests.get", side_effect=[r1, r2]) as get:
        out = await TLSImpersonateScraper().fetch_page(
            "https://linkedin.com/jobs", headers={"Cookie": "li_at=SECRET"}
        )

    assert out == "ok"
    assert "Cookie" in get.call_args_list[0].kwargs["headers"]
    assert "Cookie" not in get.call_args_list[1].kwargs["headers"]


@pytest.mark.unit
async def test_invalidate_jobs_count_cache_bumps_version_without_keys(fake_redis):
    await invalidate_jobs_count_cache(fake_redis)
    await invalidate_jobs_count_cache(fake_redis)
    assert await fake_redis.get(JOBS_COUNT_VERSION_KEY) == "2"


@pytest.mark.unit
def test_sponsorship_with_or_without_not_flagged_as_no_sponsorship():
    res = classify_sponsorship(
        "SWE Intern",
        "Must be legally authorized to work in the United States with or without sponsorship.",
    )
    assert res["status"] != "no_sponsorship"


@pytest.mark.unit
def test_github_parser_distinct_roles_same_url_and_1mo_date():
    md = """
    | Company | Role | Location | Application | Age |
    |---|---|---|---|---|
    | Acme | Backend Intern | Remote | [Apply](https://acme.com/careers) | 1mo |
    | Acme | Frontend Intern | Remote | [Apply](https://acme.com/careers) | 2d |
    """
    jobs, _ = _parse_markdown_tables(md, "https://github.com/test")
    assert len(jobs) == 2
    assert jobs[0].external_id != jobs[1].external_id
    assert parse_relative_date("1mo") is not None


@pytest.mark.unit
def test_skill_extractor_bounds_and_url_stripping():
    attrs = JobAttributes(
        skills=["Python", "https://evil.com/x", "x" * 50, "Go"],
        salary_min=999_999,
        salary_max=50,
        salary_period="hour",
    ).normalized()
    assert attrs.skills == ["Go", "Python"]
    assert attrs.salary_min is None
    assert attrs.salary_max == 50


@pytest.mark.unit
def test_news_parser_preserves_full_iso_timestamp():
    dt = _parse_iso_datetime("2026-11-27T14:35:00Z")
    assert dt is not None
    assert dt.hour == 14 and dt.minute == 35
