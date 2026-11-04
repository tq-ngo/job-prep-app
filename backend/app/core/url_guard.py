"""
SSRF protection for user-supplied crawl targets.

POST /api/v1/news/scrape accepts an arbitrary `url` and hands it to a Celery
worker, which fetches it from inside the container network. Without a guard
any authenticated user could reach:

  - cloud instance metadata (169.254.169.254) -> credential theft
  - internal services (postgres:5432, redis:6379, backend:8000)
  - loopback admin endpoints (flower on :5555, which has no auth)
  - file:// , gopher:// and other non-HTTP schemes

Validation happens at REQUEST time (fail fast, clear 4xx) and again at FETCH
time, because DNS can re-resolve between the two (DNS rebinding). At fetch
time the scraper also pins the connection to the addresses validated here
(`CrawlTarget.curl_resolve`), so curl can't re-resolve to something else.
"""
from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable, List, Optional
from urllib.parse import urlparse

ALLOWED_SCHEMES = {"http", "https"}

# Hostnames that must never be fetched regardless of DNS resolution.
_BLOCKED_HOSTNAMES = {
    "localhost", "localhost.localdomain", "ip6-localhost", "ip6-loopback",
    "metadata", "metadata.google.internal", "metadata.goog",
    # compose service names on the app network
    "postgres", "redis", "backend", "frontend", "nginx",
    "celery-worker", "celery-beat", "celery-flower",
}


class UnsafeUrlError(ValueError):
    """Raised when a URL targets a private, loopback or otherwise unsafe host."""


_NAT64_WELL_KNOWN = ipaddress.ip_network("64:ff9b::/96")


def _embedded_ipv4(ip: ipaddress._BaseAddress) -> Optional[ipaddress.IPv4Address]:
    """The IPv4 address an IPv6 address tunnels to, if any.

    `::ffff:127.0.0.1`, `2002:7f00:1::` (6to4) and `64:ff9b::7f00:1` (NAT64)
    all reach 127.0.0.1, and Python 3.11's `is_global` reports the NAT64 form
    as global, so each is unwrapped and judged as the IPv4 it carries.
    """
    if not isinstance(ip, ipaddress.IPv6Address):
        return None
    if ip.ipv4_mapped:
        return ip.ipv4_mapped
    if ip.sixtofour:
        return ip.sixtofour
    if ip in _NAT64_WELL_KNOWN:
        return ipaddress.IPv4Address(int(ip) & 0xFFFFFFFF)
    return None


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    """Allow only globally routable unicast addresses.

    An allowlist (`is_global`) rather than the old deny-list of private /
    loopback / link-local classes, which let through e.g. 100.64.0.0/10
    (carrier-grade NAT, home of Alibaba Cloud's 100.100.100.200 metadata).
    """
    ip = _embedded_ipv4(ip) or ip
    return ip.is_global and not ip.is_multicast


def _resolve(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Cannot resolve host {hostname!r}: {exc}") from exc
    return {ipaddress.ip_address(info[4][0]) for info in infos}


@dataclass(frozen=True)
class CrawlTarget:
    """A validated URL plus the public addresses its host resolved to."""

    url: str
    host: str
    port: int
    ips: List[str]

    def curl_resolve(self) -> List[str]:
        """A CURLOPT_RESOLVE entry pinning `host:port` to the vetted IPs."""
        try:
            ipaddress.ip_address(self.host)
            return []  # a literal IP needs no DNS, so there's nothing to pin
        except ValueError:
            pass
        addrs = ",".join(f"[{ip}]" if ":" in ip else ip for ip in self.ips)
        return [f"{self.host}:{self.port}:{addrs}"]


def resolve_crawl_target(raw_url: str, allowed_hosts: Optional[set] = None) -> CrawlTarget:
    """
    Validate `raw_url` (see validate_crawl_url) and return it with the
    addresses that passed, so the caller can connect to exactly those.
    Blocking: does a DNS lookup, so call it via asyncio.to_thread from async code.
    """
    if not raw_url or len(raw_url) > 2048:
        raise UnsafeUrlError("URL is empty or unreasonably long")

    parsed = urlparse(raw_url.strip())

    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise UnsafeUrlError(
            f"Scheme {parsed.scheme!r} is not allowed (only http/https)"
        )

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise UnsafeUrlError("URL has no host")
    if hostname in _BLOCKED_HOSTNAMES:
        raise UnsafeUrlError(f"Host {hostname!r} is not permitted")

    if allowed_hosts is not None:
        if not any(
            hostname == a or hostname.endswith("." + a) for a in allowed_hosts
        ):
            raise UnsafeUrlError(f"Host {hostname!r} is not on the allowlist")

    # A literal IP, or whatever the hostname resolves to right now.
    ips = sorted(_resolve(hostname), key=str)
    for ip in ips:
        if not _is_public_ip(ip):
            raise UnsafeUrlError(
                f"Host {hostname!r} resolves to non-public address {ip}"
            )

    try:
        port = parsed.port or (443 if parsed.scheme.lower() == "https" else 80)
    except ValueError as exc:
        raise UnsafeUrlError(f"Invalid port in URL: {exc}") from exc

    return CrawlTarget(
        url=raw_url.strip(),
        host=hostname,
        port=port,
        ips=[str(ip) for ip in ips],
    )


def validate_crawl_url(raw_url: str, allowed_hosts: Optional[set] = None) -> str:
    """
    Return the URL if it is safe to fetch, else raise UnsafeUrlError.

    `allowed_hosts`, when given, is an exact-match allowlist applied on top of
    the public-IP checks (defence in depth, not instead of).
    """
    return resolve_crawl_target(raw_url, allowed_hosts).url
