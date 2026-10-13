import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.core.auth_cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    REFRESH_COOKIE,
    await_rotation_result,
    claim_rotation,
    clear_auth_cookies,
    deny_token,
    is_payload_revoked,
    revoke_family,
    set_auth_cookies,
    store_rotation_result,
)
from app.core.database import get_session
from app.core.datetime_utils import utc_now
from app.core.google_oauth import (
    OAuthError,
    build_authorization_url,
    consume_state,
    exchange_code,
    verify_id_token,
)
from app.core.rate_limit import limiter
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    new_token_family,
    verify_password,
)
from app.models.users import User
from app.schemas.user import UserCreate, UserRead, UserUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

# Kept so Swagger still offers a bearer flow, and so existing bearer clients
# keep working during the migration to cookies. auto_error=False because a
# cookie is now the primary transport.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Constant-time guard for the "no such user" branch of /login.
_DUMMY_HASH = get_password_hash("not-a-real-password-placeholder")

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    session: AsyncSession = Depends(get_session),
) -> User:
    """
    Resolve the caller from an HttpOnly cookie, falling back to a bearer header.

    Cookie is preferred; the Authorization header remains accepted so API
    clients and the interactive docs keep working.
    """
    raw = access_token or token
    if not raw:
        raise _CREDENTIALS_EXC

    try:
        payload = decode_token(raw, TOKEN_TYPE_ACCESS)
    except TokenError:
        raise _CREDENTIALS_EXC

    # Revocation check: the token itself, or its whole sign-in family.
    if await is_payload_revoked(payload):
        raise _CREDENTIALS_EXC

    result = await session.execute(select(User).where(User.email == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _CREDENTIALS_EXC
    return user


async def require_csrf(request: Request) -> None:
    """
    Double-submit CSRF check for cookie-authenticated state changes.

    SameSite=Lax already blocks cross-site POSTs in modern browsers; this is
    the second layer, and it matters because CORS runs with
    allow_credentials=True.  Skipped for bearer-token callers, which are not
    subject to CSRF (the browser won't attach an Authorization header on its
    own).
    """
    if request.headers.get("authorization"):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


def _safe_next(next_path: Optional[str], default: str = "/jobs") -> str:
    """
    Accept only same-origin relative paths, so `next` can't be an open redirect.

    Backslashes are rejected too: browsers normalise `/\\evil.com` to
    `//evil.com`, a protocol-relative URL to another host.
    """
    if (
        next_path
        and next_path.startswith("/")
        and not next_path.startswith("//")
        and "\\" not in next_path
        and not any(ord(c) < 0x20 for c in next_path)
    ):
        return next_path
    return default


def _mint(email: str, family: str) -> Tuple[str, str, str]:
    """Mint an (access, refresh, csrf) triple within one token family."""
    access, _, _ = create_access_token(email, family)
    refresh, _, _ = create_refresh_token(email, family)
    return access, refresh, secrets.token_urlsafe(32)


async def _issue_session(response: Response, user: User, session: AsyncSession) -> dict:
    """Start a new token family for a fresh sign-in, set cookies, stamp last_login_at."""
    access, refresh, csrf = _mint(user.email, new_token_family())
    set_auth_cookies(response, access, refresh, csrf)

    user.last_login_at = utc_now()
    session.add(user)
    await session.commit()

    # Body no longer carries the token — it lives only in the HttpOnly cookie.
    return {"status": "ok", "csrf_token": csrf}


# ── Local email/password ────────────────────────────────────────────────

@router.post("/register", response_model=UserRead)
@limiter.limit("5/hour")
async def register(
    request: Request,
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    existing = await session.execute(select(User).where(User.email == user_in.email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password),
        skills=[],
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


@router.post("/login")
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: AsyncSession = Depends(get_session),
):
    result = await session.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    # Always run bcrypt, even with no matching user: returning early otherwise
    # made response latency a reliable oracle for which emails are registered.
    hashed = user.hashed_password if user and user.hashed_password else _DUMMY_HASH
    pwd_ok = verify_password(form_data.password, hashed)

    # The raw email is deliberately not logged (was at INFO on every attempt).
    if not user or not user.hashed_password or not pwd_ok or not user.is_active:
        logger.warning("Failed login attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return await _issue_session(response, user, session)


# ── Google OAuth 2.0 ────────────────────────────────────────────────────

def _require_google_configured() -> None:
    if not settings.google_oauth_configured:
        raise HTTPException(
            status_code=503,
            detail="Google sign-in is not configured on this deployment "
                   "(set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET).",
        )


@router.get("/google/login")
@limiter.limit("20/minute")
async def google_login(request: Request, next: str = "/jobs"):
    """Start the Google consent flow."""
    _require_google_configured()
    url = await build_authorization_url(_safe_next(next))
    return RedirectResponse(url, status_code=307)


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    Handle Google's redirect: verify state, exchange the code, verify the
    id_token, then upsert the user and set session cookies.
    """
    _require_google_configured()

    if error:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=access_denied")

    try:
        stored = await consume_state(state or "")
        if not code:
            raise OAuthError("Missing authorization code")
        tokens = await exchange_code(code, stored["code_verifier"])
        raw_id_token = tokens.get("id_token")
        if not raw_id_token:
            raise OAuthError("Token response contained no id_token")
        claims = verify_id_token(raw_id_token)
    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s", exc)
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=oauth_failed")

    email = claims["email"].lower()
    google_sub = claims["sub"]

    # Look up by google_sub first: a Google account's email can change, but
    # `sub` is stable for the life of the account.
    user = (
        await session.execute(select(User).where(User.google_sub == google_sub))
    ).scalar_one_or_none()

    if user is None:
        user = (
            await session.execute(select(User).where(User.email == email))
        ).scalar_one_or_none()
        if user is not None:
            # Link Google to the existing local account. Safe only because
            # verify_id_token already required email_verified.
            user.google_sub = google_sub
        else:
            user = User(email=email, google_sub=google_sub, skills=[])

    user.full_name = user.full_name or claims.get("name")
    user.avatar_url = claims.get("picture") or user.avatar_url
    session.add(user)
    await session.commit()
    await session.refresh(user)

    if not user.is_active:
        return RedirectResponse(f"{settings.FRONTEND_URL}/login?error=account_disabled")

    redirect = RedirectResponse(
        f"{settings.FRONTEND_URL}{stored.get('next', '/jobs')}", status_code=303
    )
    await _issue_session(redirect, user, session)
    return redirect


# ── Session lifecycle ───────────────────────────────────────────────────

class _RefreshFailed(Exception):
    """The refresh cookie can't be exchanged; the caller must sign in again."""


# How long a concurrent caller presenting an already-rotated refresh token
# still receives the pair minted for it (multi-tab refresh races).
_ROTATION_GRACE_SECONDS = 30


async def _rotate_refresh(
    raw_refresh: Optional[str], session: AsyncSession
) -> Tuple[str, str, str]:
    """
    Exchange a refresh token for a new (access, refresh, csrf) triple.

    Each refresh token is single-use. A reuse inside the grace window is a
    concurrent tab and gets the same new pair; a reuse after it is a replayed
    (likely stolen) token, so the whole family is revoked — logging out both
    the thief and the victim, who then signs in again.
    """
    if not raw_refresh:
        raise _RefreshFailed("No refresh token")
    try:
        payload = decode_token(raw_refresh, TOKEN_TYPE_REFRESH)
    except TokenError:
        raise _RefreshFailed("Invalid refresh token")
    if await is_payload_revoked(payload):
        raise _RefreshFailed("Refresh token revoked")

    jti = payload["jti"]
    # Tokens minted before families existed fall back to their own jti.
    family = payload.get("fam") or jti
    remaining = int(payload["exp"] - datetime.now(timezone.utc).timestamp())

    if not await claim_rotation(jti, remaining):
        cached = await await_rotation_result(jti)
        if cached:
            return cached
        logger.warning("Refresh token reuse outside grace window; revoking family")
        await revoke_family(family, settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
        await deny_token(jti, remaining)
        raise _RefreshFailed("Refresh token already used")

    result = await session.execute(select(User).where(User.email == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise _RefreshFailed("User not found or disabled")

    tokens = _mint(user.email, family)
    await store_rotation_result(jti, tokens, _ROTATION_GRACE_SECONDS)
    return tokens


@router.post("/refresh")
@limiter.limit("60/hour")
async def refresh_session(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    """Rotate the refresh token and issue a new access token."""
    try:
        access, refresh, csrf = await _rotate_refresh(refresh_token, session)
    except _RefreshFailed as exc:
        # Build the 401 directly: headers set on the injected `response` are
        # discarded when an HTTPException is raised, so the old code's
        # clear_auth_cookies() calls never reached the browser.
        failed = JSONResponse(status_code=401, content={"detail": str(exc)})
        clear_auth_cookies(failed)
        return failed

    set_auth_cookies(response, access, refresh, csrf)
    return {"status": "ok", "csrf_token": csrf}


@router.get("/resume")
@limiter.limit("30/minute")
async def resume_session(
    request: Request,
    next: str = "/jobs",
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    """
    Navigation-time refresh, used by the Next.js edge proxy.

    The access cookie lives 15 minutes and the refresh cookie is scoped to
    /api/v1/auth, so a full page load of /jobs after an idle spell has no
    usable credential the proxy can see — it used to bounce straight to
    /login despite a valid 30-day refresh token. The proxy now redirects
    here instead; this path receives the refresh cookie, rotates it, and
    sends the browser back.

    A GET that rotates tokens is CSRF-triggerable under SameSite=Lax, but the
    only effect is rotating the victim's own session, which is harmless.
    """
    target = _safe_next(next)
    try:
        access, refresh, csrf = await _rotate_refresh(refresh_token, session)
    except _RefreshFailed:
        to_login = RedirectResponse(f"/login?next={quote(target)}", status_code=303)
        clear_auth_cookies(to_login)
        return to_login

    back = RedirectResponse(target, status_code=303)
    set_auth_cookies(back, access, refresh, csrf)
    return back


@router.post("/logout")
async def logout(
    response: Response,
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
):
    """Revoke both tokens and the sign-in family, and clear the cookies."""
    now = datetime.now(timezone.utc).timestamp()
    for raw, kind in ((access_token, TOKEN_TYPE_ACCESS), (refresh_token, TOKEN_TYPE_REFRESH)):
        if not raw:
            continue
        try:
            payload = decode_token(raw, kind)
        except TokenError:
            continue
        ttl = int(payload["exp"] - now)
        await deny_token(payload["jti"], ttl)
        # Revoking the family also kills any rotation result still held for
        # the grace window, and tokens another tab may have just minted.
        if payload.get("fam"):
            await revoke_family(payload["fam"], settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)

    clear_auth_cookies(response)
    return {"status": "logged_out"}


# ── Current user ────────────────────────────────────────────────────────

@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me/skills", response_model=UserRead)
async def update_skills(
    skills_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    current_user.skills = [s.strip().lower() for s in skills_in.skills if s.strip()]
    session.add(current_user)
    await session.commit()
    await session.refresh(current_user)
    return current_user
