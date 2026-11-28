import asyncio
import pytest

from app.scraping.jd_extractor import (
    sanitize_html_to_markdown,
    MIN_JD_CHARS,
    MAX_JD_CHARS,
)


@pytest.mark.unit
def test_sanitize_html_to_markdown_removes_dangerous_elements():
    # Construct an HTML description >= MIN_JD_CHARS (200 chars)
    payload = """
    <div>
        <h2>Software Engineering Intern - 2026</h2>
        <p>We are seeking high-caliber SWE interns to build cutting-edge distributed storage infrastructure.</p>
        <script>evil_attack();</script>
        <iframe src="http://attacker.com"></iframe>
        <img src="https://tracker.pixel.io/track.gif" width="1" height="1" />
        <picture><source srcset="tracker.png"></picture>
        <form action="/phish"><input type="text" name="pw"/></form>
        <h3>Qualifications:</h3>
        <ul>
            <li>Experience in Python, Go, C++, or Rust.</li>
            <li>Solid grasp of concurrency, data structures, and algorithms.</li>
            <li>Strong collaborative skills and intellectual curiosity.</li>
        </ul>
    </div>
    """
    assert len(payload) > MIN_JD_CHARS
    result = sanitize_html_to_markdown(payload)

    assert result is not None
    assert "evil_attack" not in result
    assert "iframe" not in result
    assert "tracker.pixel.io" not in result
    assert "input" not in result
    assert "form" not in result
    # Structural headings and lists should survive
    assert "## Software Engineering Intern" in result
    assert "Experience in Python" in result


@pytest.mark.unit
def test_sanitize_html_to_markdown_enforces_minimum_length():
    short_boilerplate = "<p>Too short description for real posting.</p>"
    assert len(short_boilerplate) < MIN_JD_CHARS
    assert sanitize_html_to_markdown(short_boilerplate) is None
    assert sanitize_html_to_markdown("") is None
    assert sanitize_html_to_markdown(None) is None


@pytest.mark.unit
def test_sanitize_html_to_markdown_enforces_maximum_length():
    # Long text over 40,000 chars
    long_content = (
        "<p>Engineering Role</p>\n" + ("<p>Detailed requirement block line.</p>\n" * 1500)
    )
    assert len(long_content) > MAX_JD_CHARS
    result = sanitize_html_to_markdown(long_content)
    assert result is not None
    assert "_[description truncated]_" in result
    assert len(result) <= MAX_JD_CHARS + 50


@pytest.mark.unit
async def test_domain_rate_limiter_distinct_domains():
    import time
    from app.scraping.jd_extractor import DomainRateLimiter

    limiter = DomainRateLimiter(default_per_domain_limit=2, default_interval=0.1)
    start = time.monotonic()

    # Acquire across 4 distinct domains concurrently
    await asyncio.gather(
        limiter.acquire("domain1.com"),
        limiter.acquire("domain2.com"),
        limiter.acquire("domain3.com"),
        limiter.acquire("domain4.com"),
    )
    elapsed = time.monotonic() - start

    # Across distinct domains, there should be virtually no spacing delay
    assert elapsed < 0.2

    limiter.release("domain1.com")
    limiter.release("domain2.com")
    limiter.release("domain3.com")
    limiter.release("domain4.com")


@pytest.mark.unit
async def test_enrich_with_descriptions_intra_batch_dedup():
    from unittest.mock import patch
    from app.scraping.jd_extractor import enrich_with_descriptions

    # 3 records with identical apply_url (e.g. from 3 different GitHub repos)
    records = [
        {"apply_url": "https://boards.greenhouse.io/corp/jobs/1", "source": "github", "external_id": "id-1", "description": None},
        {"apply_url": "https://boards.greenhouse.io/corp/jobs/1", "source": "github", "external_id": "id-2", "description": None},
        {"apply_url": "https://boards.greenhouse.io/corp/jobs/1", "source": "github", "external_id": "id-3", "description": None},
    ]

    fetch_call_count = 0

    async def mock_fetch_jd_with_source(apply_url, source, external_id):
        nonlocal fetch_call_count
        fetch_call_count += 1
        return "## Mock Description", "greenhouse"

    with patch("app.scraping.jd_extractor.fetch_jd_with_source", side_effect=mock_fetch_jd_with_source):
        filled = await enrich_with_descriptions(records)

    # All 3 records should be filled
    assert filled == 3
    for r in records:
        assert r["description"] == "## Mock Description"
        assert r["description_source"] == "greenhouse"

    # But network fetch was only called ONCE for the shared apply_url!
    assert fetch_call_count == 1


@pytest.mark.unit
async def test_from_generic_rejects_cookie_banner_boilerplate():
    from unittest.mock import AsyncMock, patch
    from app.scraping.jd_extractor import _from_generic

    cookie_only_html = """
    <html><body>
      <div id="onetrust-consent-sdk">
        <p>Cookies allow websites to make your Internet experience better. Accept all cookies or manage cookie preferences.</p>
      </div>
      <div class="consent-banner">
        <p>Cookies allow websites to make your Internet experience better and personalize content across our site. We use cookies to analyze traffic.</p>
      </div>
    </body></html>
    """
    with patch("app.scraping.jd_extractor.http_scraper.fetch_page", new=AsyncMock(return_value=cookie_only_html)):
        md, strategy = await _from_generic("https://careers.waymo.com/jobs/123")
    assert md is None
    assert strategy is None


@pytest.mark.unit
async def test_from_generic_strips_cookie_banner_and_keeps_real_jd():
    from unittest.mock import AsyncMock, patch
    from app.scraping.jd_extractor import _from_generic

    mixed_html = """
    <html><body>
      <div id="onetrust-consent-sdk">
        <p>Cookies allow websites to make your Internet experience better. Accept all cookies.</p>
      </div>
      <main>
        <h1>Software Engineering Intern</h1>
        <p>Join our core infrastructure team to build distributed services in Python and Go.</p>
        <h2>Responsibilities</h2>
        <ul>
          <li>Design and implement scalable backend APIs and data pipelines.</li>
          <li>Collaborate with mentors across engineering teams during your internship.</li>
        </ul>
      </main>
    </body></html>
    """
    with patch("app.scraping.jd_extractor.http_scraper.fetch_page", new=AsyncMock(return_value=mixed_html)):
        md, strategy = await _from_generic("https://example.com/jobs/123")
    assert strategy == "readability"
    assert md is not None
    assert "Cookies allow websites" not in md
    assert "Software Engineering Intern" in md


