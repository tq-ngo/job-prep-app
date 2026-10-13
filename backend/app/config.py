from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, model_validator


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str = Field(
        ...,  # "..." means required — no default
        description="PostgreSQL connection URL (asyncpg dialect)",
    )
    REDIS_URL: str = Field(...)
    CELERY_BROKER_URL: str = Field(...)
    CELERY_RESULT_BACKEND: str = Field(...)

    GEMINI_API_KEY: str = Field(default="")
    GEMINI_MODEL: str = Field(default="gemini-3.8-flash")
    EMBEDDING_MODEL: str = Field(default="text-embedding-004")
    # Celery rate limit for enrich_job_with_ai. Each job costs TWO Gemini
    # calls (skill extraction + embedding).
    #
    # IMPORTANT — the binding constraint is the DAILY quota, not the per-minute
    # one. Observed on the free tier for gemini-3.8-flash:
    #     GenerateRequestsPerMinutePerProjectPerModel-FreeTier = 5 / min
    #     GenerateRequestsPerDayPerProjectPerModel-FreeTier    = 20 / DAY
    # 20 requests/day is ~10 enriched jobs/day against a crawl of ~125-375
    # jobs/day, so AI enrichment CANNOT keep up on the free tier regardless of
    # this setting. A paid plan is required for the feature to function; until
    # then the board still works, jobs just carry no skills/embeddings.
    GEMINI_RATE_LIMIT: str = Field(default="2/m")

    SECRET_KEY: str = Field(...)

    APP_ENV: str = Field(default="development")
    CORS_ORIGINS: str = Field(default="http://localhost")

    # Single source of truth for JWT settings. core/security.py previously
    # declared its own local ALGORITHM / ACCESS_TOKEN_EXPIRE_MINUTES and used
    # those instead, so changing these values here had no effect.
    ALGORITHM: str = "HS256"
    # Was 7 days for a single non-revocable token. Short-lived access tokens
    # bound the damage from a leaked one; the refresh token carries longevity.
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Cookies ──────────────────────────────────────────────────────────
    # Tokens move from localStorage (readable by any XSS) into HttpOnly
    # cookies. Secure defaults to off only so plain-HTTP localhost dev works;
    # it MUST be true in production.
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: str = "lax"
    COOKIE_DOMAIN: str = ""

    # ── Google OAuth 2.0 ─────────────────────────────────────────────────
    # Empty by default so the app still boots without Google credentials;
    # the /auth/google/* routes return 503 until these are set.
    GOOGLE_CLIENT_ID: str = Field(default="")
    GOOGLE_CLIENT_SECRET: str = Field(default="")
    GOOGLE_REDIRECT_URI: str = Field(
        default="http://localhost/api/v1/auth/google/callback"
    )
    # Public origin of the app (nginx). The browser, the API and the OAuth
    # callback all share it, so cookies set by the callback are visible to the
    # Next.js edge proxy.
    FRONTEND_URL: str = Field(default="http://localhost")

    @model_validator(mode="after")
    def _require_secure_cookies_off_localhost(self) -> "Settings":
        # A Secure=false session cookie on an HTTPS site is sent over any
        # plain-HTTP request to the same host (e.g. a downgrade), so refuse to
        # boot rather than run that way silently.
        if not self.COOKIE_SECURE and (
            self.APP_ENV == "production" or self.FRONTEND_URL.startswith("https://")
        ):
            raise ValueError(
                "COOKIE_SECURE must be true when APP_ENV=production or "
                "FRONTEND_URL is https://"
            )
        # HS256 keys shorter than the hash output are brute-forceable
        # (RFC 7518 §3.2), and the same key now also signs-checks at the edge.
        if self.APP_ENV == "production" and len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be at least 32 characters in production")
        return self

    @property
    def google_oauth_configured(self) -> bool:
        return bool(self.GOOGLE_CLIENT_ID and self.GOOGLE_CLIENT_SECRET)


settings = Settings()