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
time, because DNS can re-resolve between the two (DNS rebinding).
"""
from __future__ import annotations

import ipaddress
import socket
from typing import Iterable, Optional
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


def _is_public_ip(ip: ipaddress._BaseAddress) -> bool:
    """Reject every non-globally-routable address class."""
    return not (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local      # 169.254.0.0/16 -> cloud metadata
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def _resolve(hostname: str) -> Iterable[ipaddress._BaseAddress]:
    try:
        infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as exc:
        raise UnsafeUrlError(f"Cannot resolve host {hostname!r}: {exc}") from exc
    return {ipaddress.ip_address(info[4][0]) for info in infos}


def validate_crawl_url(raw_url: str, allowed_hosts: Optional[set] = None) -> str:
    """
    Return the URL if it is safe to fetch, else raise UnsafeUrlError.

    `allowed_hosts`, when given, is an exact-match allowlist applied on top of
    the public-IP checks (defence in depth, not instead of).
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
    for ip in _resolve(hostname):
        if not _is_public_ip(ip):
            raise UnsafeUrlError(
                f"Host {hostname!r} resolves to non-public address {ip}"
            )

    return raw_url.strip()
