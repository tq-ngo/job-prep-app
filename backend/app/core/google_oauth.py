"""
Google OAuth 2.0 authorization-code flow with PKCE.

The previous codebase had no third-party OAuth of any kind: `OAuth2PasswordBearer`
is the RFC-6749 *password grant* form parser, not Google sign-in.

Security properties implemented here:
  - `state`         : random, stored server-side in Redis, single-use -> CSRF
                      protection on the callback
  - browser binding : a second random value set as an HttpOnly cookie on the
                      browser that started the flow and stored with the
                      state. Without it, a callback URL from an attacker's
                      own flow, opened by a victim, signed the victim into
                      the attacker's account (login CSRF).
  - PKCE (S256)     : binds the authorization code to this specific client, so
                      an intercepted code is useless
  - id_token verify : signature checked against Google's JWKS, plus issuer,
                      audience and expiry (google-auth does all of it)
  - email_verified  : unverified Google emails are rejected, otherwise anyone
                      could claim an address they don't control
  - nonce (OIDC)    : random per-request value stored with the state and
                      echoed inside the signed id_token, so an id_token
                      minted for some other authorization request can't be
                      replayed into this callback
"""
import base64
import hashlib
import json
import logging
import secrets
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode

import httpx
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token

from app.config import settings
from app.core.redis import get_redis_pool

logger = logging.getLogger(__name__)

AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

_STATE_PREFIX = "oauth:state:"
_STATE_TTL_SECONDS = 600  # 10 minutes to complete the round trip

BINDING_COOKIE = "oauth_binding"
# Sent only to the callback, never to the rest of the API.
BINDING_COOKIE_PATH = "/api/v1/auth/google"


class OAuthError(Exception):
    """Raised when the OAuth exchange fails or a response can't be trusted."""


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


async def build_authorization_url(next_path: str = "/jobs") -> Tuple[str, str]:
    """
    Create the Google consent URL and stash state + PKCE verifier in Redis.

    State is kept server-side (not in a cookie) so the callback can verify it
    exactly once; Redis DEL on read makes replay impossible.

    Returns (url, binding). The caller must set `binding` as the
    BINDING_COOKIE on the response that redirects to Google.
    """
    state = _b64url(secrets.token_bytes(32))
    nonce = _b64url(secrets.token_bytes(32))
    binding = _b64url(secrets.token_bytes(32))
    code_verifier = _b64url(secrets.token_bytes(64))
    code_challenge = _b64url(hashlib.sha256(code_verifier.encode()).digest())

    redis = await get_redis_pool()
    await redis.setex(
        f"{_STATE_PREFIX}{state}",
        _STATE_TTL_SECONDS,
        json.dumps({
            "code_verifier": code_verifier,
            "next": next_path,
            "nonce": nonce,
            "binding": binding,
        }),
    )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "access_type": "online",
        "prompt": "select_account",
    }
    return f"{AUTH_ENDPOINT}?{urlencode(params)}", binding


async def consume_state(state: str, binding: Optional[str]) -> Dict[str, Any]:
    """
    Atomically fetch-and-delete the stored state, then check it belongs to
    this browser. Raises if unknown, expired, or started elsewhere.

    The state is consumed even on a binding mismatch, so a leaked callback
    URL is dead after one try.
    """
    if not state:
        raise OAuthError("Missing state parameter")
    redis = await get_redis_pool()
    key = f"{_STATE_PREFIX}{state}"
    # GETDEL is a single atomic command. A separate GET then DEL let two
    # concurrent callbacks carrying the same state both read it before
    # either deleted it.
    raw = await redis.getdel(key)
    if raw is None:
        # Unknown, expired, or already used -> treat as CSRF / replay.
        raise OAuthError("Invalid or expired state parameter")
    stored = json.loads(raw)
    expected = stored.get("binding")
    if not expected or not binding or not secrets.compare_digest(binding, expected):
        raise OAuthError("OAuth flow was not started by this browser")
    return stored


async def exchange_code(code: str, code_verifier: str) -> Dict[str, Any]:
    """Exchange an authorization code for tokens."""
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            TOKEN_ENDPOINT,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": settings.GOOGLE_REDIRECT_URI,
                "grant_type": "authorization_code",
                "code_verifier": code_verifier,
            },
            headers={"Accept": "application/json"},
        )
    if resp.status_code != 200:
        # Never log the body verbatim: it can echo the client secret.
        raise OAuthError(f"Token exchange failed with HTTP {resp.status_code}")
    return resp.json()


def verify_id_token(raw_id_token: str, expected_nonce: Optional[str] = None) -> Dict[str, Any]:
    """
    Verify Google's id_token and return its claims.

    google-auth fetches Google's JWKS and validates the signature, `iss`,
    `aud` and `exp`. Verifying locally (rather than calling a tokeninfo
    endpoint) avoids an extra network hop on every login.

    `expected_nonce` is the value stored with the state. It is optional only
    so that a sign-in already in flight when this check shipped (its state
    record predates the nonce) still completes; every new flow stores one.
    """
    try:
        claims = google_id_token.verify_oauth2_token(
            raw_id_token,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise OAuthError(f"id_token verification failed: {exc}") from exc

    if claims.get("iss") not in ("accounts.google.com", "https://accounts.google.com"):
        raise OAuthError("Unexpected id_token issuer")
    if expected_nonce is not None and not secrets.compare_digest(
        str(claims.get("nonce") or ""), expected_nonce
    ):
        raise OAuthError("id_token nonce mismatch")
    if not claims.get("email"):
        raise OAuthError("id_token contains no email")
    if not claims.get("email_verified"):
        # Without this check, a Google account holding an unverified address
        # could be used to claim someone else's account by email match.
        raise OAuthError("Google account email is not verified")
    if not claims.get("sub"):
        raise OAuthError("id_token contains no subject")
    return claims
