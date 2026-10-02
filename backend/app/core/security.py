"""
Password hashing and JWT issuance/verification.

Token model (replaces a single 7-day, non-revocable access token):

    access  — 15 min, sent on every request
    refresh — 30 days, rotated on each use, revocable

Every token carries a `jti`, so a specific token can be revoked via a Redis
denylist. Previously the payload held only {sub, exp}: no jti meant tokens
were structurally unrevocable for their full 7-day life, and there was no
refresh endpoint, logout, or denylist at all.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import uuid

import bcrypt
from jose import jwt, JWTError

from app.config import settings

# Single source of truth is config.py. security.py used to declare its own
# copies of these and silently win over the settings values.
ALGORITHM = settings.ALGORITHM
ACCESS_TOKEN_EXPIRE_MINUTES = settings.ACCESS_TOKEN_EXPIRE_MINUTES
REFRESH_TOKEN_EXPIRE_DAYS = settings.REFRESH_TOKEN_EXPIRE_DAYS

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"

# Claims pinned on every token so a token minted for one purpose can't be
# replayed against another.
_ISSUER = "job-prep-app"
_AUDIENCE = "job-prep-app:api"


class TokenError(Exception):
    """Raised when a token is malformed, expired, or of the wrong type."""


def verify_password(plain_password: str, hashed_password: Optional[str]) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    if not hashed_password:
        return False
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:72],
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt (12 rounds)."""
    return bcrypt.hashpw(
        password.encode("utf-8")[:72],
        bcrypt.gensalt(rounds=12),
    ).decode("utf-8")


def _create_token(subject: str, token_type: str, expires_delta: timedelta) -> tuple[str, str, datetime]:
    """Mint a signed JWT. Returns (token, jti, expiry)."""
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    payload: Dict[str, Any] = {
        "sub": subject,
        "typ": token_type,
        "jti": jti,
        "iat": now,
        "nbf": now,
        "exp": expire,
        "iss": _ISSUER,
        "aud": _AUDIENCE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM), jti, expire


def create_access_token(subject: str, expires_delta: Optional[timedelta] = None):
    return _create_token(
        subject,
        TOKEN_TYPE_ACCESS,
        expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str, expires_delta: Optional[timedelta] = None):
    return _create_token(
        subject,
        TOKEN_TYPE_REFRESH,
        expires_delta or timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str, expected_type: str) -> Dict[str, Any]:
    """
    Verify a token's signature and claims, and assert its type.

    `algorithms` is pinned to a single value so a token with `alg: none`
    (or an attacker-chosen algorithm) is rejected outright.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[ALGORITHM],
            audience=_AUDIENCE,
            issuer=_ISSUER,
        )
    except JWTError as exc:
        raise TokenError(f"Invalid token: {exc}") from exc

    if payload.get("typ") != expected_type:
        # Stops a refresh token being presented as an access token.
        raise TokenError(
            f"Expected a {expected_type} token, got {payload.get('typ')!r}"
        )
    if not payload.get("sub"):
        raise TokenError("Token has no subject")
    return payload
