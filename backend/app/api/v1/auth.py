import asyncio
import hashlib
import logging
import secrets
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import quote

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from redis.exceptions import RedisError
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
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
    delete_rotation_result,
    deny_token,
    is_payload_revoked,
    revoke_family,
    set_auth_cookies,
    store_rotation_result,
)
from app.core.database import get_session
from app.core.datetime_utils import utc_now
from app.core.google_oauth import (
    BINDING_COOKIE,
    BINDING_COOKIE_PATH,
    OAuthError,
    build_authorization_url,
    consume_state,
    exchange_code,
    verify_id_token,
)
from app.core.rate_limit import limiter
from app.core.redis import get_redis_pool
from app.core.security import (
    TOKEN_TYPE_ACCESS,
    TOKEN_TYPE_REFRESH,
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    get_password_hash,
    get_password_hash_async,
    new_token_family,
    verify_password_async,
)
from app.core.user_cache import (
    check_revocation_and_get_profile,
    invalidate_user_profile,
    set_cached_user_profile,
    to_user_model,
)
from app.models.users import User
from app.schemas.user import UserCreate, UserRead, UserUpdate, normalize_email

logger = logging.getLogger(__name__)

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

# Constant-time guard for the "no such user" branch of /login.
_DUMMY_HASH = get_password_hash("not-a-real-password-placeholder")

_CREDENTIALS_EXC = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)

# Per-email credential-stuffing lockout thresholds.
_LOGIN_FAIL_PREFIX = "auth:fail:"
_LOGIN_FAIL_LIMIT = 10
_LOGIN_FAIL_WINDOW_SECONDS = 900


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    session: AsyncSession = Depends(get_session),
) -> User:
    """Resolve the caller from an HttpOnly cookie, falling back to a bearer header."""
    raw = access_token or token
    if not raw:
        raise _CREDENTIALS_EXC

    try:
        payload = decode_token(raw, TOKEN_TYPE_ACCESS)
    except TokenError:
        raise _CREDENTIALS_EXC

    is_revoked, cached_profile = await check_revocation_and_get_profile(payload)
    if is_revoked:
        raise _CREDENTIALS_EXC

    token_ver = payload.get("ver")

    if cached_profile is not None:
        if not cached_profile.is_active:
            raise _CREDENTIALS_EXC
        if token_ver is not None and cached_profile.token_version != token_ver:
            raise _CREDENTIALS_EXC
        return to_user_model(cached_profile)

    result = await session.execute(select(User).where(User.email == payload["sub"]))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        await invalidate_user_profile(payload["sub"])
        raise _CREDENTIALS_EXC
    if token_ver is not None and user.token_version != token_ver:
        await invalidate_user_profile(payload["sub"])
        raise _CREDENTIALS_EXC
    await set_cached_user_profile(user)
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Enforce administrative privileges on operational trigger endpoints."""
    if not getattr(current_user, "is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator privileges required",
        )
    return current_user


async def require_csrf(request: Request) -> None:
    """Double-submit CSRF check for cookie-authenticated state changes."""
    has_auth_cookie = bool(
        request.cookies.get(ACCESS_COOKIE) or request.cookies.get(REFRESH_COOKIE)
    )
    if not has_auth_cookie and request.headers.get("authorization"):
        return
    cookie_token = request.cookies.get(CSRF_COOKIE)
    header_token = request.headers.get(CSRF_HEADER)
    if not cookie_token or not header_token:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    if not secrets.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")


def _check_same_origin(request: Request) -> None:
    """Mitigate Login CSRF on browser form submissions."""
    sec_fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if sec_fetch_site == "cross-site":
        raise HTTPException(status_code=403, detail="Cross-site request rejected")
    origin = (request.headers.get("origin") or "").strip()
    if origin and origin not in settings.cors_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")


def _email_fail_key(email: str) -> str:
    digest = hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()[:32]
    return f"{_LOGIN_FAIL_PREFIX}{digest}"


async def _check_email_lockout(email: str) -> None:
    try:
        redis = await get_redis_pool()
        count = int(await redis.get(_email_fail_key(email)) or 0)
        if count >= _LOGIN_FAIL_LIMIT:
            ttl = await redis.ttl(_email_fail_key(email))
            headers = {"Retry-After": str(max(1, int(ttl)))} if ttl and ttl > 0 else None
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many failed login attempts. Please try again later.",
                headers=headers,
            )
    except HTTPException:
        raise
    except RedisError as exc:
        logger.warning("Email lockout check failed; continuing: %s", exc)


async def _record_email_failure(email: str) -> None:
    try:
        redis = await get_redis_pool()
        key = _email_fail_key(email)
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, _LOGIN_FAIL_WINDOW_SECONDS)
            await pipe.execute()
    except RedisError as exc:
        logger.warning("Failed to record login failure counter: %s", exc)


async def _clear_email_failures(email: str) -> None:
    try:
        redis = await get_redis_pool()
        await redis.delete(_email_fail_key(email))
    except RedisError:
        pass


async def _find_user_by_email(session: AsyncSession, email: str) -> Optional[User]:
    """Case-insensitive lookup for sign-in paths."""
    result = await session.execute(
        select(User)
        .where(func.lower(User.email) == normalize_email(email))
        .order_by(User.id)
        .limit(1)
    )
    return result.scalar_one_or_none()


def _safe_next(next_path: Optional[str], default: str = "/jobs") -> str:
    """Accept only same-origin relative paths, so `next` can't be an open redirect."""
    if (
        next_path
        and next_path.startswith("/")
        and not next_path.startswith("//")
        and "\\" not in next_path
        and not any(ord(c) < 0x20 or ord(c) == 0x7F for c in next_path)
    ):
        return next_path
    return default


def _mint(email: str, family: str, token_version: int = 1) -> Tuple[str, str, str]:
    """Mint an (access, refresh, csrf) triple within one token family."""
    access, _, _ = create_access_token(email, family, token_version=token_version)
    refresh, _, _ = create_refresh_token(email, family, token_version=token_version)
    return access, refresh, secrets.token_urlsafe(32)


async def _issue_session(response: Response, user: User, session: AsyncSession) -> dict:
    """Start a new token family for a fresh sign-in, set cookies, stamp last_login_at."""
    access, refresh, csrf = _mint(
        user.email,
        new_token_family(),
        token_version=int(getattr(user, "token_version", 1) or 1),
    )
    set_auth_cookies(response, access, refresh, csrf)
    response.headers["Cache-Control"] = "private, no-store"

    user.last_login_at = utc_now()
    session.add(user)
    await session.commit()
    await set_cached_user_profile(user)

    return {"status": "ok", "csrf_token": csrf}


# ── Local email/password ────────────────────────────────────────────────

@router.post("/register", response_model=UserRead)
@limiter.limit("5/hour")
async def register(
    request: Request,
    response: Response,
    user_in: UserCreate,
    session: AsyncSession = Depends(get_session),
):
    response.headers["Cache-Control"] = "private, no-store"
    if await _find_user_by_email(session, user_in.email):
        await get_password_hash_async(user_in.password)
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_in.email,
        hashed_password=await get_password_hash_async(user_in.password),
        skills=[],
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(status_code=400, detail="Email already registered")
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
    _check_same_origin(request)
    response.headers["Cache-Control"] = "private, no-store"
    await _check_email_lockout(form_data.username)

    user = await _find_user_by_email(session, form_data.username)

    hashed = user.hashed_password if user and user.hashed_password else _DUMMY_HASH
    pwd_ok = await verify_password_async(form_data.password, hashed)

    if not user or not user.hashed_password or not pwd_ok or not user.is_active:
        await _record_email_failure(form_data.username)
        logger.warning("Failed login attempt")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    await _clear_email_failures(form_data.username)
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
    url, binding = await build_authorization_url(_safe_next(next))
    redirect = RedirectResponse(url, status_code=307)
    redirect.headers["Cache-Control"] = "private, no-store"
    redirect.set_cookie(
        BINDING_COOKIE,
        binding,
        max_age=600,
        path=BINDING_COOKIE_PATH,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
    )
    return redirect


def _oauth_redirect(url: str, status_code: int = 307) -> RedirectResponse:
    """A callback redirect that also clears the single-use binding cookie."""
    redirect = RedirectResponse(url, status_code=status_code)
    redirect.headers["Cache-Control"] = "private, no-store"
    redirect.delete_cookie(BINDING_COOKIE, path=BINDING_COOKIE_PATH)
    return redirect


def _oauth_error_url(code: str, next_path: Optional[str] = None) -> str:
    base = f"{settings.FRONTEND_URL}/login?error={code}"
    if next_path and next_path != "/jobs":
        safe = _safe_next(next_path, default="")
        if safe:
            return f"{base}&next={quote(safe)}"
    return base


@router.get("/google/callback")
@limiter.limit("20/minute")
async def google_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    oauth_binding: Optional[str] = Cookie(default=None, alias=BINDING_COOKIE),
    session: AsyncSession = Depends(get_session),
):
    """Handle Google's redirect: verify state, exchange code, verify id_token, upsert user."""
    _require_google_configured()

    if error:
        return _oauth_redirect(_oauth_error_url("access_denied"))

    stored: dict = {}
    try:
        stored = await consume_state(state or "", oauth_binding)
        if not code:
            raise OAuthError("Missing authorization code")
        tokens = await exchange_code(code, stored["code_verifier"])
        raw_id_token = tokens.get("id_token")
        if not raw_id_token:
            raise OAuthError("Token response contained no id_token")
        claims = await asyncio.to_thread(
            verify_id_token, raw_id_token, stored.get("nonce")
        )
    except OAuthError as exc:
        logger.warning("Google OAuth failed: %s", exc)
        return _oauth_redirect(_oauth_error_url("oauth_failed", stored.get("next")))

    next_target = _safe_next(stored.get("next"), default="/jobs")
    email = normalize_email(claims["email"])
    google_sub = claims["sub"]

    user = (
        await session.execute(select(User).where(User.google_sub == google_sub))
    ).scalar_one_or_none()

    if user is None:
        if await _find_user_by_email(session, email) is not None:
            logger.info("Google sign-in refused: email belongs to another account")
            return _oauth_redirect(
                _oauth_error_url("account_exists", next_target), status_code=303
            )
        user = User(email=email, google_sub=google_sub, skills=[])
    elif not user.is_active:
        return _oauth_redirect(_oauth_error_url("account_disabled", next_target))

    user.full_name = user.full_name or claims.get("name")
    user.avatar_url = claims.get("picture") or user.avatar_url
    session.add(user)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("Google sign-in race: account email/sub already exists")
        return _oauth_redirect(
            _oauth_error_url("account_exists", next_target), status_code=303
        )
    await session.refresh(user)

    redirect = _oauth_redirect(
        f"{settings.FRONTEND_URL}{next_target}", status_code=303
    )
    await _issue_session(redirect, user, session)
    return redirect


# ── Session lifecycle ───────────────────────────────────────────────────

class _RefreshFailed(Exception):
    """The refresh cookie can't be exchanged; the caller must sign in again."""


# Narrow multi-tab refresh race grace window (bounded reads in auth_cookies.py).
_ROTATION_GRACE_SECONDS = 5


async def _rotate_refresh(
    raw_refresh: Optional[str], session: AsyncSession
) -> Tuple[str, str, str]:
    """Exchange a refresh token for a new (access, refresh, csrf) triple."""
    if not raw_refresh:
        raise _RefreshFailed("No refresh token")
    try:
        payload = decode_token(raw_refresh, TOKEN_TYPE_REFRESH)
    except TokenError:
        raise _RefreshFailed("Invalid refresh token")
    if await is_payload_revoked(payload):
        raise _RefreshFailed("Refresh token revoked")

    jti = payload["jti"]
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
        await invalidate_user_profile(payload["sub"])
        raise _RefreshFailed("User not found or disabled")
    token_ver = payload.get("ver")
    if token_ver is not None and user.token_version != token_ver:
        await invalidate_user_profile(payload["sub"])
        raise _RefreshFailed("Session invalidated")

    await set_cached_user_profile(user)
    tokens = _mint(user.email, family, token_version=int(user.token_version or 1))
    await store_rotation_result(jti, tokens, _ROTATION_GRACE_SECONDS)
    return tokens


@router.post("/refresh")
@limiter.limit("60/hour")
async def refresh_session(
    request: Request,
    response: Response,
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    """Rotate the refresh token and issue a new access token."""
    try:
        access, refresh, csrf = await _rotate_refresh(refresh_token, session)
    except _RefreshFailed as exc:
        failed = JSONResponse(
            status_code=401,
            content={"detail": str(exc)},
            headers={"Cache-Control": "private, no-store"},
        )
        clear_auth_cookies(failed)
        return failed

    set_auth_cookies(response, access, refresh, csrf)
    response.headers["Cache-Control"] = "private, no-store"
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

    Rejects cross-site top-level GET navigations (Sec-Fetch-Site: cross-site
    or same-site) so third-party origins cannot trigger silent token rotations.
    """
    target = _safe_next(next)
    sec_fetch_site = (request.headers.get("sec-fetch-site") or "").strip().lower()
    if sec_fetch_site and sec_fetch_site not in ("same-origin", "none"):
        reject = RedirectResponse(f"/login?next={quote(target)}", status_code=303)
        reject.headers["Cache-Control"] = "private, no-store"
        return reject

    try:
        access, refresh, csrf = await _rotate_refresh(refresh_token, session)
    except _RefreshFailed:
        to_login = RedirectResponse(f"/login?next={quote(target)}", status_code=303)
        to_login.headers["Cache-Control"] = "private, no-store"
        clear_auth_cookies(to_login)
        return to_login

    back = RedirectResponse(target, status_code=303)
    back.headers["Cache-Control"] = "private, no-store"
    set_auth_cookies(back, access, refresh, csrf)
    return back


@router.post("/logout")
@limiter.limit("30/minute")
async def logout(
    request: Request,
    response: Response,
    bearer_token: Optional[str] = Depends(oauth2_scheme),
    access_token: Optional[str] = Cookie(default=None, alias=ACCESS_COOKIE),
    refresh_token: Optional[str] = Cookie(default=None, alias=REFRESH_COOKIE),
    _: None = Depends(require_csrf),
):
    """Revoke cookie and/or bearer tokens and the sign-in family, and clear cookies."""
    now = datetime.now(timezone.utc).timestamp()
    subjects = set()
    candidates = (
        (access_token, TOKEN_TYPE_ACCESS),
        (bearer_token, TOKEN_TYPE_ACCESS),
        (refresh_token, TOKEN_TYPE_REFRESH),
    )
    for raw, kind in candidates:
        if not raw:
            continue
        try:
            payload = decode_token(raw, kind)
        except TokenError:
            continue
        ttl = int(payload["exp"] - now)
        await deny_token(payload["jti"], ttl)
        if kind == TOKEN_TYPE_REFRESH:
            await delete_rotation_result(payload["jti"])
        if payload.get("fam"):
            await revoke_family(payload["fam"], settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 3600)
        subjects.add(payload["sub"])

    for sub in subjects:
        await invalidate_user_profile(sub)

    clear_auth_cookies(response)
    response.headers["Cache-Control"] = "private, no-store"
    return {"status": "logged_out"}


# ── Current user ────────────────────────────────────────────────────────

@router.get("/me", response_model=UserRead)
@limiter.limit("120/minute")
async def get_me(
    request: Request,
    response: Response,
    current_user: User = Depends(get_current_user),
):
    response.headers["Cache-Control"] = "private, no-store"
    return current_user


@router.put("/me/skills", response_model=UserRead)
@limiter.limit("30/minute")
async def update_skills(
    request: Request,
    response: Response,
    skills_in: UserUpdate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
    _: None = Depends(require_csrf),
):
    response.headers["Cache-Control"] = "private, no-store"
    user = await session.get(User, current_user.id)
    if user is None or not user.is_active:
        await invalidate_user_profile(current_user.email)
        raise _CREDENTIALS_EXC

    user.skills = skills_in.skills
    session.add(user)
    await session.commit()
    await session.refresh(user)
    await set_cached_user_profile(user)
    return user
