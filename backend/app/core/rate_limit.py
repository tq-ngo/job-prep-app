"""
Request rate limiting.

/login and /register previously had no limiting and no lockout, leaving an
unbounded credential-stuffing surface on a 7-day, non-revocable token. The
scrape triggers were likewise unbounded: any authenticated user could spam
Celery dispatch (the Redis NX lock made that mostly harmless, but it is still
free queue pressure).

Storage is Redis so limits are shared across API replicas rather than being
per-process.
"""
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

logger = logging.getLogger(__name__)


def _client_key(request) -> str:
    """
    Identify the caller for limiting purposes.

    Prefers the left-most X-Forwarded-For entry because the app sits behind
    nginx, where get_remote_address() would otherwise see the proxy's IP and
    bucket every user together.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return get_remote_address(request)


limiter = Limiter(
    key_func=_client_key,
    storage_uri=settings.REDIS_URL,
    strategy="fixed-window",
)
