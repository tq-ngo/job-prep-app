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


@pytest.mark.integration
async def test_job_feed_sponsorship_filtering_and_domain(
    client: AsyncClient,
    mock_db_session: AsyncSession,
    auth_headers: dict,
):
    j_us = Job(
        id=uuid.uuid4(),
        external_id="motorola-spons-1",
        source="github",
        title="Software Engineering Intern",
        company="Motorola Solutions",
        company_domain="motorolasolutions.com",
        category="Others",
        apply_url="https://motorolasolutions.com/careers/1",
        is_active=True,
        canonical_id=None,
        description="You are a U.S. Citizen, U.S. permanent resident or possess other unrestricted US work authorization.",
    )
    j_no = Job(
        id=uuid.uuid4(),
        external_id="nbc-spons-2",
        source="github",
        title="Software Engineer Intern",
        company="NBCUniversal",
        company_domain="nbcuniversal.com",
        category="Others",
        apply_url="https://nbcuniversal.com/careers/2",
        is_active=True,
        canonical_id=None,
        description="Must not require work visa sponsorship. F-1 CPT and OPT students are not eligible.",
    )
    j_avail = Job(
        id=uuid.uuid4(),
        external_id="stripe-spons-3",
        source="github",
        title="Backend Engineering Intern",
        company="Stripe",
        company_domain="stripe.com",
        category="Others",
        apply_url="https://stripe.com/careers/3",
        is_active=True,
        canonical_id=None,
        description="Visa sponsorship is available for eligible candidates. We sponsor H-1B visas.",
    )
    mock_db_session.add_all([j_us, j_no, j_avail])
    await mock_db_session.commit()

    # Filter requires_citizenship
    res_us = await client.get(
        "/api/v1/jobs/",
        params={"sponsorship": "requires_citizenship"},
        cookies=auth_headers["cookies"],
    )
    assert res_us.status_code == 200
    us_data = res_us.json()
    assert us_data["total"] == 1
    assert us_data["items"][0]["company"] == "Motorola Solutions"
    assert us_data["items"][0]["company_domain"] == "motorolasolutions.com"
    assert us_data["items"][0]["sponsorship_status"] == "citizenship"
    assert us_data["items"][0]["sponsorship_label"] == "US Citizen Required"

    # Filter no_sponsorship
    res_no = await client.get(
        "/api/v1/jobs/",
        params={"sponsorship": "no_sponsorship"},
        cookies=auth_headers["cookies"],
    )
    assert res_no.status_code == 200
    no_data = res_no.json()
    assert no_data["total"] == 1
    assert no_data["items"][0]["company"] == "NBCUniversal"
    assert no_data["items"][0]["sponsorship_status"] == "no_sponsorship"
    assert no_data["items"][0]["sponsorship_label"] == "No Sponsorship"

    # Filter sponsorship_available
    res_avail = await client.get(
        "/api/v1/jobs/",
        params={"sponsorship": "sponsorship_available"},
        cookies=auth_headers["cookies"],
    )
    assert res_avail.status_code == 200
    avail_data = res_avail.json()
    assert avail_data["total"] == 1
    assert avail_data["items"][0]["company"] == "Stripe"
    assert avail_data["items"][0]["sponsorship_status"] == "sponsorship_available"
    assert avail_data["items"][0]["sponsorship_label"] == "Sponsorship Available"

