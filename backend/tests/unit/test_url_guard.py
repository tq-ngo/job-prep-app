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



@pytest.mark.unit
@pytest.mark.parametrize(
    "address",
    [
        "100.100.100.200",   # CGNAT range; Alibaba Cloud metadata
        "100.64.0.1",
        "::ffff:127.0.0.1",  # IPv4-mapped loopback
        "::ffff:169.254.169.254",
        "2002:7f00:1::",     # 6to4 wrapping 127.0.0.1
        "64:ff9b::7f00:1",   # NAT64 wrapping 127.0.0.1; is_global=True on 3.11
        "fc00::1",           # IPv6 unique-local
        "224.0.0.1",         # multicast
        "0.0.0.0",
    ],
)
def test_url_guard_blocks_non_global_addresses(address: str):
    with patch(
        "app.core.url_guard._resolve",
        return_value=[ipaddress.ip_address(address)],
    ):
        with pytest.raises(UnsafeUrlError, match="resolves to non-public address"):
            validate_crawl_url("http://sneaky.example/")


@pytest.mark.unit
def test_url_guard_rejects_if_any_resolved_address_is_private():
    # One public A record must not launder a private one alongside it.
    with patch(
        "app.core.url_guard._resolve",
        return_value=[
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("10.0.0.5"),
        ],
    ):
        with pytest.raises(UnsafeUrlError):
            validate_crawl_url("http://mixed.example/")


@pytest.mark.unit
def test_resolve_crawl_target_pins_vetted_addresses():
    from app.core.url_guard import resolve_crawl_target

    with patch(
        "app.core.url_guard._resolve",
        return_value=[
            ipaddress.ip_address("93.184.216.34"),
            ipaddress.ip_address("2606:2800:220:1::1"),
        ],
    ):
        target = resolve_crawl_target("https://example.com/jobs/1")

    assert target.host == "example.com"
    assert target.port == 443
    assert target.curl_resolve() == [
        "example.com:443:[2606:2800:220:1::1],93.184.216.34"
    ]


@pytest.mark.unit
def test_resolve_crawl_target_literal_ip_needs_no_pin():
    from app.core.url_guard import resolve_crawl_target

    target = resolve_crawl_target("http://93.184.216.34:8080/x")
    assert target.port == 8080
    assert target.curl_resolve() == []
