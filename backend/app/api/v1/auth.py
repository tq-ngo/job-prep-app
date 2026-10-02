import logging
import secrets
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.config import settings
from app.core.auth_cookies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    CSRF_HEADER,
    REFRESH_COOKIE,
    clear_auth_cookies,
    deny_token,
    is_token_denied,
    set_auth_cookies,
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

    # Revocation check — impossible before, since tokens carried no jti.
    if await is_token_denied(payload.get("jti")):
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


async def _issue_session(response: Response, user: User, session: AsyncSession) -> dict:
    """Mint tokens, set cookies, and stamp last_login_at."""
    access, _, _ = create_access_token(user.email)
    refresh, _, _ = create_refresh_token(user.email)
    csrf = secrets.token_urlsafe(32)
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
    # Only accept relative paths, so `next` can't be used as an open redirect.
    safe_next = next if next.startswith("/") and not next.startswith("//") else "/jobs"
    url = await build_authorization_url(safe_next)
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

@router.post("/refresh")
@limiter.limit("60/hour")
async def refresh_session(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    """
    Rotate the refresh token and issue a new access token.

    The presented refresh token is denylisted immediately, so each one is
    single-use: replaying a stolen token after the legitimate client has
    refreshed will fail.
    """
    if not refresh_token:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="No refresh token")
    try:
        payload = decode_token(refresh_token, TOKEN_TYPE_REFRESH)
    except TokenError:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    if await is_token_denied(payload.get("jti")):
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="Refresh token already used")

    result = await session.execute(select(User).where(User.email == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        clear_auth_cookies(response)
        raise HTTPException(status_code=401, detail="User not found or disabled")

    remaining = int(payload["exp"] - datetime.now(timezone.utc).timestamp())
    await deny_token(payload["jti"], remaining)

    return await _issue_session(response, user, session)


@router.post("/logout")
async def logout(
    response: Response,
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
):
    """Revoke both tokens and clear the cookies."""
    now = datetime.now(timezone.utc).timestamp()
    for raw, kind in ((access_token, TOKEN_TYPE_ACCESS), (refresh_token, TOKEN_TYPE_REFRESH)):
        if not raw:
            continue
        try:
            payload = decode_token(raw, kind)
        except TokenError:
            continue
        await deny_token(payload["jti"], int(payload["exp"] - now))

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
