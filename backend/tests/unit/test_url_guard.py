import pytest
from unittest.mock import patch
import ipaddress

from app.core.url_guard import validate_crawl_url, UnsafeUrlError


@pytest.mark.unit
@pytest.mark.parametrize(
    "blocked_host",
    [
        "localhost",
        "metadata",
        "metadata.google.internal",
        "postgres",
        "redis",
        "backend",
        "frontend",
        "nginx",
        "celery-worker",
        "celery-beat",
    ],
)
def test_url_guard_blocks_internal_hosts(blocked_host: str):
    url = f"http://{blocked_host}/internal-api"
    with pytest.raises(UnsafeUrlError, match="Host .* is not permitted"):
        validate_crawl_url(url)


@pytest.mark.unit
@pytest.mark.parametrize(
    "invalid_scheme",
    [
        "file:///etc/passwd",
        "gopher://example.com",
        "ftp://files.example.com",
        "javascript:alert(1)",
    ],
)
def test_url_guard_blocks_invalid_schemes(invalid_scheme: str):
    with pytest.raises(UnsafeUrlError, match="Scheme .* is not allowed"):
        validate_crawl_url(invalid_scheme)


@pytest.mark.unit
def test_url_guard_empty_or_too_long():
    with pytest.raises(UnsafeUrlError, match="URL is empty or unreasonably long"):
        validate_crawl_url("")

    with pytest.raises(UnsafeUrlError, match="URL is empty or unreasonably long"):
        validate_crawl_url("https://example.com/" + "a" * 2050)


@pytest.mark.unit
def test_url_guard_blocks_private_and_link_local_ips():
    # Mock DNS resolution to return private or link-local IPs
    with patch(
        "app.core.url_guard._resolve",
        return_value=[ipaddress.ip_address("169.254.169.254")],
    ):
        with pytest.raises(UnsafeUrlError, match="resolves to non-public address"):
            validate_crawl_url("http://cloud-metadata-spoofed.com/")

    with patch(
        "app.core.url_guard._resolve",
        return_value=[ipaddress.ip_address("10.0.0.1")],
    ):
        with pytest.raises(UnsafeUrlError, match="resolves to non-public address"):
            validate_crawl_url("http://internal-corp-network.com/")

    with patch(
        "app.core.url_guard._resolve",
        return_value=[ipaddress.ip_address("127.0.0.1")],
    ):
        with pytest.raises(UnsafeUrlError, match="resolves to non-public address"):
            validate_crawl_url("http://local-spoof.com/")


@pytest.mark.unit
def test_url_guard_allows_public_urls():
    with patch(
        "app.core.url_guard._resolve",
        return_value=[ipaddress.ip_address("93.184.216.34")],
    ):
        valid = validate_crawl_url("https://example.com/jobs/123")
        assert valid == "https://example.com/jobs/123"


@pytest.mark.unit
def test_url_guard_allowed_hosts_whitelist():
    with patch(
        "app.core.url_guard._resolve",
        return_value=[ipaddress.ip_address("93.184.216.34")],
    ):
        # Allowed host match
        assert (
            validate_crawl_url(
                "https://boards.greenhouse.io/job", allowed_hosts={"greenhouse.io"}
            )
            == "https://boards.greenhouse.io/job"
        )

        # Host outside allowlist
        with pytest.raises(UnsafeUrlError, match="Host .* is not on the allowlist"):
            validate_crawl_url(
                "https://other-domain.com/job", allowed_hosts={"greenhouse.io"}
            )

