"""
TLSImpersonateScraper redirect handling and SSRF checks.

curl_cffi isn't httpx, so respx can't intercept it; `requests.get` is
patched directly and DNS goes through a patched url_guard._resolve.
"""
import ipaddress
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from curl_cffi import CurlOpt

from app.scraping.http_scraper import TLSImpersonateScraper

PUBLIC = ipaddress.ip_address("93.184.216.34")
PRIVATE = ipaddress.ip_address("10.0.0.7")


def _response(status: int, text: str = "", location: str | None = None):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.headers = {"location": location} if location else {}
    return resp


@pytest.fixture
def breaker():
    cb = MagicMock()
    cb.allow_request = AsyncMock(return_value=True)
    cb.record_success = AsyncMock()
    cb.record_failure = AsyncMock()
    with patch("app.scraping.http_scraper.circuit_breaker", cb):
        yield cb


def _resolver(mapping: dict):
    def resolve(host):
        return [mapping[host]]
    return resolve


@pytest.mark.unit
async def test_follows_safe_redirect_and_pins_each_hop(breaker):
    responses = [
        _response(302, location="https://jobs.example.org/posting/1"),
        _response(200, text="<html>JD</html>"),
    ]
    with patch(
        "app.core.url_guard._resolve",
        side_effect=_resolver({"example.com": PUBLIC, "jobs.example.org": PUBLIC}),
    ), patch("app.scraping.http_scraper.requests.get", side_effect=responses) as get:
        text = await TLSImpersonateScraper().fetch_page("https://example.com/apply")

    assert text == "<html>JD</html>"
    pins = [call.kwargs["curl_options"][CurlOpt.RESOLVE] for call in get.call_args_list]
    assert pins == [
        ["example.com:443:93.184.216.34"],
        ["jobs.example.org:443:93.184.216.34"],
    ]
    breaker.record_success.assert_awaited_once_with("jobs.example.org")


@pytest.mark.unit
async def test_blocks_redirect_to_private_address(breaker):
    with patch(
        "app.core.url_guard._resolve",
        side_effect=_resolver({"example.com": PUBLIC, "internal.example.com": PRIVATE}),
    ), patch(
        "app.scraping.http_scraper.requests.get",
        return_value=_response(302, location="http://internal.example.com/admin"),
    ) as get:
        text = await TLSImpersonateScraper().fetch_page("https://example.com/apply")

    assert text is None
    assert get.call_count == 1  # the private hop is never requested


@pytest.mark.unit
async def test_redirect_without_location_is_terminal(breaker):
    with patch("app.core.url_guard._resolve", return_value=[PUBLIC]), patch(
        "app.scraping.http_scraper.requests.get", return_value=_response(302)
    ) as get:
        text = await TLSImpersonateScraper().fetch_page("https://example.com/x")

    assert text is None
    assert get.call_count == 1  # not retried


@pytest.mark.unit
async def test_proxy_disables_pinning(breaker):
    with patch("app.core.url_guard._resolve", return_value=[PUBLIC]), patch(
        "app.scraping.http_scraper.requests.get", return_value=_response(200, "ok")
    ) as get:
        await TLSImpersonateScraper(proxy_url="http://proxy:3128").fetch_page(
            "https://example.com/x"
        )

    assert get.call_args.kwargs["curl_options"] is None


@pytest.mark.unit
async def test_retries_charge_breaker_once(breaker):
    with patch("app.core.url_guard._resolve", return_value=[PUBLIC]), patch(
        "app.scraping.http_scraper.requests.get", return_value=_response(429)
    ) as get, patch("app.scraping.http_scraper.asyncio.sleep", new=AsyncMock()):
        text = await TLSImpersonateScraper().fetch_page("https://example.com/x", max_retries=3)

    assert text is None
    assert get.call_count == 3
    # One failure per fetch, and one breaker check (a HALF_OPEN probe slot
    # would refuse our own second attempt otherwise).
    breaker.record_failure.assert_awaited_once_with("example.com")
    breaker.allow_request.assert_awaited_once_with("example.com")
