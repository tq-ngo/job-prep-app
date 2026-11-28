import asyncio
import logging
import re
import time
import weakref
from typing import Optional, Type, TypeVar
from pydantic import BaseModel
from redis.exceptions import WatchError
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

SchemaT = TypeVar("SchemaT", bound=BaseModel)

# One Gemini client per live event loop using WeakKeyDictionary so closed
# Celery task loops are garbage-collected cleanly without `id(loop)` reuse
# collisions or leaking transports across tasks.
_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, genai.Client]" = (
    weakref.WeakKeyDictionary()
)
_fallback_client: Optional[genai.Client] = None
_HTTP_TIMEOUT_MS = 30_000


def _build_client() -> genai.Client:
    return genai.Client(
        api_key=settings.GEMINI_API_KEY,
        http_options=types.HttpOptions(timeout=_HTTP_TIMEOUT_MS),
    )


def _get_client() -> genai.Client:
    global _fallback_client
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        if _fallback_client is None:
            _fallback_client = _build_client()
        return _fallback_client

    client = _clients.get(loop)
    if client is None:
        client = _build_client()
        _clients[loop] = client
    return client


def _build_thinking_config(thinking_budget: Optional[int]) -> Optional[types.ThinkingConfig]:
    """
    Build a model-compatible ThinkingConfig.

    Gemini 3.x models use `thinking_level` (`LOW`/`MEDIUM`/`HIGH`) and reject
    `thinking_budget=0` with 400 INVALID_ARGUMENT; Gemini 2.5 models use
    `thinking_budget`.
    """
    if thinking_budget is None:
        return None
    model_lower = (settings.GEMINI_MODEL or "").lower()
    if "gemini-3" in model_lower:
        return types.ThinkingConfig(thinking_level=types.ThinkingLevel.LOW)
    return types.ThinkingConfig(thinking_budget=thinking_budget)


class GeminiTransientError(RuntimeError):
    """
    Raised on retryable upstream faults (429 rate limit, 503 high demand).
    """

    def __init__(self, message: str, retry_after: Optional[int] = None, is_daily_quota: bool = False):
        super().__init__(message)
        self.retry_after = retry_after
        self.is_daily_quota = is_daily_quota


class GeminiThrottled(GeminiTransientError):
    """
    Raised by acquire_gemini_slots when the shared per-minute budget or daily
    cooldown is active. No upstream call was made.
    """


_SLOTS_PREFIX = "gemini:slots:"
_DAILY_COOLDOWN_KEY = "gemini:daily_cooldown"
_SLOT_WINDOW_SECONDS = 60
_MAX_WATCH_RETRIES = 5


async def set_daily_quota_cooldown(redis, seconds: int = 900) -> None:
    """Pause background Gemini calls when daily quota is exhausted."""
    try:
        await redis.setex(_DAILY_COOLDOWN_KEY, max(60, int(seconds)), "1")
    except Exception as exc:
        logger.warning("Failed to record Gemini daily cooldown: %s", exc)


async def acquire_gemini_slots(redis, n: int = 1) -> None:
    """
    Atomically reserve `n` Gemini calls from the project-wide per-minute
    budget (settings.GEMINI_REQUESTS_PER_MINUTE), or raise GeminiThrottled.

    Uses WATCH/MULTI/EXEC so concurrent callers cannot overshoot or leak
    reservations on crash, while remaining compatible with fakeredis.
    """
    limit = settings.GEMINI_REQUESTS_PER_MINUTE
    if limit <= 0:
        return
    if n > limit:
        raise GeminiConfigError(
            f"One operation needs {n} Gemini calls but GEMINI_REQUESTS_PER_MINUTE={limit}"
        )

    cooldown_ttl = await redis.ttl(_DAILY_COOLDOWN_KEY)
    if cooldown_ttl and cooldown_ttl > 0:
        raise GeminiThrottled(
            "Gemini daily quota cooldown active", retry_after=int(cooldown_ttl), is_daily_quota=True
        )

    now = time.time()
    key = f"{_SLOTS_PREFIX}{int(now // _SLOT_WINDOW_SECONDS)}"
    retry_after = int(_SLOT_WINDOW_SECONDS - now % _SLOT_WINDOW_SECONDS) + 1

    for _ in range(_MAX_WATCH_RETRIES):
        async with redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(key)
                current = int(await pipe.get(key) or 0)
                if current + n > limit:
                    await pipe.unwatch()
                    raise GeminiThrottled(
                        f"Gemini budget of {limit}/min spent", retry_after=retry_after
                    )
                pipe.multi()
                pipe.incrby(key, n)
                pipe.expire(key, _SLOT_WINDOW_SECONDS * 2)
                await pipe.execute()
                return
            except WatchError:
                continue

    raise GeminiThrottled(
        f"Gemini budget contention on {limit}/min window", retry_after=2
    )


class GeminiTruncatedError(RuntimeError):
    """Raised when the response hit the output-token ceiling."""


class GeminiConfigError(RuntimeError):
    """Raised when Gemini fails due to deployment/model/auth configuration."""


# Substrings that identify a configuration fault rather than a content fault.
_CONFIG_FAULT_MARKERS = (
    "not found",
    "was not found",
    "is not supported",
    "api key not valid",
    "no api key",           # google-genai raises this when GEMINI_API_KEY is empty
    "api_key_invalid",
    "permission denied",
    "permission_denied",
    "unauthenticated",
    "billing",
    "invalid_argument",
    "quota",
)


# Retryable upstream conditions. Checked BEFORE config markers, because a 429
# message can mention "quota" while still being transient.
_TRANSIENT_MARKERS = (
    "503",
    "unavailable",
    "high demand",
    "429",
    "rate limit",
    "resource_exhausted",
    "deadline",
    "timeout",
)

_DAILY_QUOTA_MARKERS = (
    "perday",
    "per day",
    "daily",
    "rpd",
)


def _classify(exc: Exception) -> Exception:
    """Map an SDK exception onto our transient/config/other taxonomy."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(marker in text for marker in _TRANSIENT_MARKERS):
        match = re.search(r"'retryDelay':\s*'(\d+)s'", str(exc))
        retry_after = int(match.group(1)) if match else None
        is_daily = any(marker in text for marker in _DAILY_QUOTA_MARKERS)
        return GeminiTransientError(
            f"Gemini temporarily unavailable: {exc}",
            retry_after=retry_after,
            is_daily_quota=is_daily,
        )
    if any(marker in text for marker in _CONFIG_FAULT_MARKERS):
        return GeminiConfigError(
            f"Gemini configuration fault (model={settings.GEMINI_MODEL!r}, embedding={settings.EMBEDDING_MODEL!r}): {exc}"
        )
    return exc


async def verify_model() -> None:
    """
    Assert at startup that both GEMINI_MODEL and EMBEDDING_MODEL resolve.

    Fails fast on deterministic configuration/auth/404 faults; logs a warning
    (without blocking boot) on transient upstream 503/429/timeout blips.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning(
            "GEMINI_API_KEY is empty — AI enrichment and news summarization "
            "will be skipped. Set it to enable them."
        )
        return

    for label, model_name in (
        ("GEMINI_MODEL", settings.GEMINI_MODEL),
        ("EMBEDDING_MODEL", settings.EMBEDDING_MODEL),
    ):
        try:
            await _get_client().aio.models.get(model=model_name)
            logger.info("%s %r resolved OK", label, model_name)
        except Exception as exc:
            classified = _classify(exc)
            if isinstance(classified, GeminiTransientError):
                logger.warning(
                    "Could not verify %s=%r due to transient error (continuing boot): %s",
                    label,
                    model_name,
                    classified,
                )
                continue
            raise GeminiConfigError(
                f"{label}={model_name!r} did not resolve: {exc}. "
                f"Check the model ID and that the API key has access to it."
            ) from exc


async def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.1,
    max_tokens: int = 1024,
    thinking_budget: Optional[int] = 0,
) -> str:
    """Call Gemini for text generation using google-genai SDK."""
    config_kwargs = dict(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    thinking_cfg = _build_thinking_config(thinking_budget)
    if thinking_cfg is not None:
        config_kwargs["thinking_config"] = thinking_cfg

    try:
        response = await _get_client().aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as exc:
        raise _classify(exc) from exc

    candidate = (response.candidates or [None])[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    text = response.text or ""

    if finish_reason is not None and str(finish_reason).endswith("MAX_TOKENS"):
        thoughts = getattr(response.usage_metadata, "thoughts_token_count", None)
        raise GeminiTruncatedError(
            f"Response hit max_output_tokens={max_tokens} "
            f"(thinking_budget={thinking_budget}, thoughts_token_count={thoughts})."
        )
    if not text.strip():
        raise GeminiTruncatedError(
            f"Gemini returned empty text (finish_reason={finish_reason}, "
            f"max_tokens={max_tokens}, thinking_budget={thinking_budget})."
        )
    return text


async def generate_structured(
    prompt: str,
    schema: Type[SchemaT],
    system_instruction: str = "",
    temperature: float = 0.0,
    max_tokens: int = 2048,
) -> SchemaT:
    """Call Gemini with a response schema and return the validated model."""
    config_kwargs = dict(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_tokens,
        response_mime_type="application/json",
        response_schema=schema,
    )
    thinking_cfg = _build_thinking_config(0)
    if thinking_cfg is not None:
        config_kwargs["thinking_config"] = thinking_cfg

    try:
        response = await _get_client().aio.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
    except Exception as exc:
        raise _classify(exc) from exc

    candidate = (response.candidates or [None])[0]
    finish_reason = getattr(candidate, "finish_reason", None)
    if finish_reason is not None and str(finish_reason).endswith("MAX_TOKENS"):
        raise GeminiTruncatedError(f"Structured response hit max_output_tokens={max_tokens}")
    if isinstance(response.parsed, schema):
        return response.parsed
    text = response.text or ""
    if not text.strip():
        raise GeminiTruncatedError(f"Gemini returned empty text (finish_reason={finish_reason}).")
    return schema.model_validate_json(text)
