import pytest

from app.scraping.dedup import JobDeduplicator


@pytest.mark.unit
def test_canonicalize_url_strips_tracking():
    raw_url = (
        "HTTP://Jobs.Amazon.com/pv/123/?"
        "utm_source=linkedin&utm_medium=feed&ref=banner&job_id=456&trk=direct"
    )
    canonical = JobDeduplicator.canonicalize_url(raw_url)
    assert canonical == "https://jobs.amazon.com/pv/123?job_id=456"


@pytest.mark.unit
def test_canonicalize_url_trailing_slashes_and_casing():
    raw_url = "HTTPS://WWW.EXAMPLE.COM/Careers/SWE-Intern/"
    canonical = JobDeduplicator.canonicalize_url(raw_url)
    assert canonical == "https://www.example.com/Careers/SWE-Intern"


@pytest.mark.unit
def test_normalize_text():
    assert (
        JobDeduplicator.normalize_text("  Apple, Inc. - Software (Intern)  ")
        == "apple inc software intern"
    )
    assert JobDeduplicator.normalize_text("") == ""
    assert JobDeduplicator.normalize_text(None) == ""


@pytest.mark.unit
def test_generate_fingerprint_deterministic_and_space_invariant():
    fp1 = JobDeduplicator.generate_fingerprint(
        company="Stripe",
        title="Software Engineer Intern",
        location="San Francisco, CA",
    )
    fp2 = JobDeduplicator.generate_fingerprint(
        company="  stripe  ",
        title="Software   Engineer Intern!",
        location="San Francisco CA",
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # SHA-256 hex length

