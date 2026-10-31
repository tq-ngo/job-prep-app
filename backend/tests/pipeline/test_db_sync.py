import pytest
from app.scraping.db_sync import DatabaseSyncService, _key, _member
from app.scraping.categorize import CATEGORY_FAANG


@pytest.mark.pipeline
def test_collapse_intra_batch_deduplication():
    # Construct batch containing duplicate (external_id, source)
    raw_records = [
        {"external_id": "job-1", "source": "github", "title": "SWE 1"},
        {
            "external_id": "job-1",
            "source": "github",
            "title": "SWE 1 (updated)",
        },  # duplicate
        {"external_id": "job-2", "source": "github", "title": "SWE 2"},
        {
            "external_id": "job-1",
            "source": "linkedin",
            "title": "SWE 1",
        },  # distinct source
    ]

    collapsed = DatabaseSyncService._collapse_intra_batch(raw_records)
    # job-1 github should be collapsed to 1 entry
    assert len(collapsed) == 3
    keys = [_key(r) for r in collapsed]
    assert ("job-1", "github") in keys
    assert ("job-2", "github") in keys
    assert ("job-1", "linkedin") in keys


@pytest.mark.pipeline
def test_attach_fingerprints_and_classifications():
    records = [
        {
            "external_id": "apple-101",
            "source": "github",
            "company": "Apple",
            "title": "iOS Intern",
            "location": "Cupertino, CA",
            "apply_url": "https://jobs.apple.com/us/details/101",
        }
    ]

    DatabaseSyncService._attach_fingerprints(records)
    r = records[0]

    # Fingerprint attached
    assert "canonical_hash" in r
    assert len(r["canonical_hash"]) == 64

    # Categorization attached
    assert r["category"] == CATEGORY_FAANG

    # Company domain attached
    assert r["company_domain"] == "apple.com"


@pytest.mark.pipeline
def test_key_and_member_helpers():
    record = {"external_id": "test-123", "source": "linkedin"}
    k = _key(record)
    assert k == ("test-123", "linkedin")
    assert _member(k) == "linkedin:test-123"

