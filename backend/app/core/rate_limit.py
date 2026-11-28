"""
Request rate limiting.

Storage is Redis so limits are shared across API replicas, with in-memory
fallback enabled so transient Redis outages do not turn into API-wide 500s.
"""
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)


def _client_key(request) -> str:
    """
    Identify the caller using Uvicorn's ProxyHeadersMiddleware-validated
    `request.client.host`.

    Never read raw `X-Forwarded-For` directly here: doing so lets any caller
    bypassing nginx (or hitting a dev/internal port) spoof arbitrary IPs.
    Behind nginx, Uvicorn runs with `--proxy-headers` and `FORWARDED_ALLOW_IPS`
    pinned to nginx's static IP, which safely populates `request.client.host`.
    """
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.REDIS_URL,
    strategy="moving-window",
    in_memory_fallback_enabled=True,
)
