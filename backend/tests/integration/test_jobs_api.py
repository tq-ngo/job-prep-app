import pytest
import uuid
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job


@pytest.mark.integration
async def test_job_feed_hides_duplicates_and_defers_heavy_columns(
    client: AsyncClient,
    mock_db_session: AsyncSession,
    auth_headers: dict,
):
    # Primary job
    primary = Job(
        id=uuid.uuid4(),
        external_id="stripe-101",
        source="github",
        title="Software Engineer Intern",
        company="Stripe",
        category="Others",
        apply_url="https://stripe.com/jobs/101",
        is_active=True,
        canonical_id=None,
        description="A" * 500,
    )
    mock_db_session.add(primary)
    await mock_db_session.flush()

    # Cross-source duplicate (points to primary)
    duplicate = Job(
        id=uuid.uuid4(),
        external_id="stripe-202",
        source="linkedin",
        title="Software Engineer Intern",
        company="Stripe",
        category="Others",
        apply_url="https://stripe.com/jobs/101",
        is_active=True,
        canonical_id=primary.id,  # Linked duplicate
        description="A" * 500,
    )
    mock_db_session.add(duplicate)
    await mock_db_session.commit()

    # Fetch jobs feed
    res = await client.get("/api/v1/jobs/", cookies=auth_headers["cookies"])
    assert res.status_code == 200
    data = res.json()

    # Assert total and items filter out canonical_id != NULL
    assert data["total"] == 1
    assert len(data["items"]) == 1
    item = data["items"][0]
    assert item["external_id"] == "stripe-101"

    # Assert heavy columns are deferred
    assert "description" not in item
    assert "embedding" not in item


@pytest.mark.integration
async def test_job_feed_filtering_and_search_escaping(
    client: AsyncClient,
    mock_db_session: AsyncSession,
    auth_headers: dict,
):
    j1 = Job(
        id=uuid.uuid4(),
        external_id="google-1",
        source="github",
        title="Frontend Intern",
        company="Google",
        category="FAANG+",
        is_remote=False,
        apply_url="https://google.com/careers/1",
        is_active=True,
        canonical_id=None,
    )
    j2 = Job(
        id=uuid.uuid4(),
        external_id="citadel-2",
        source="linkedin",
        title="Quant Developer Intern",
        company="Citadel",
        category="Quant",
        is_remote=True,
        apply_url="https://citadel.com/careers/2",
        is_active=True,
        canonical_id=None,
    )
    mock_db_session.add_all([j1, j2])
    await mock_db_session.commit()

    # Filter by category (httpx params properly encodes '+' as '%2B')
    res_faang = await client.get(
        "/api/v1/jobs/",
        params={"category": "FAANG+"},
        cookies=auth_headers["cookies"],
    )
    assert res_faang.status_code == 200
    assert res_faang.json()["total"] == 1
    assert res_faang.json()["items"][0]["company"] == "Google"

    # Filter by remote
    res_remote = await client.get(
        "/api/v1/jobs/",
        params={"is_remote": True},
        cookies=auth_headers["cookies"],
    )
    assert res_remote.status_code == 200
    assert res_remote.json()["total"] == 1
    assert res_remote.json()["items"][0]["company"] == "Citadel"

    # Search with SQL wildcard escaping
    res_search_wildcard = await client.get(
        "/api/v1/jobs/",
        params={"q": "%"},
        cookies=auth_headers["cookies"],
    )
    assert res_search_wildcard.status_code == 200
    # Escaped '%' should not match random company names without literal '%'
    assert res_search_wildcard.json()["total"] == 0


@pytest.mark.integration
async def test_get_job_detail_endpoint(
    client: AsyncClient,
    mock_db_session: AsyncSession,
    auth_headers: dict,
):
    job_id = uuid.uuid4()
    job = Job(
        id=job_id,
        external_id="ext-details-123",
        source="github",
        title="Platform Engineer Intern",
        company="Airbnb",
        category="Others",
        apply_url="https://airbnb.com/careers/123",
        is_active=True,
        canonical_id=None,
        description="Full markdown job description with extensive details.",
    )
    mock_db_session.add(job)
    await mock_db_session.commit()

    # Retrieve specific job
    res = await client.get(
        f"/api/v1/jobs/{job_id}", cookies=auth_headers["cookies"]
    )
    assert res.status_code == 200
    data = res.json()
    assert data["id"] == str(job_id)
    assert data["title"] == "Platform Engineer Intern"
    assert (
        data["description"]
        == "Full markdown job description with extensive details."
    )

    # 404 on non-existent job
    res_404 = await client.get(
        f"/api/v1/jobs/{uuid.uuid4()}", cookies=auth_headers["cookies"]
    )
    assert res_404.status_code == 404
