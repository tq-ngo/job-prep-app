import asyncio
import logging
import re
from typing import Optional, List
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

# The Gemini client must NOT be created at import time.
#
# google-genai's async transport binds to whichever event loop is running when
# it is first used. Celery tasks go through asgiref.async_to_sync, which spins
# up a FRESH event loop per task, so a module-level client works for exactly
# one task and every subsequent one dies with "Event loop is closed".
# Cache one client per loop instead.
_clients: dict[int, genai.Client] = {}


def _get_client() -> genai.Client:
    try:
        loop_id = id(asyncio.get_running_loop())
    except RuntimeError:
        loop_id = 0
    client = _clients.get(loop_id)
    if client is None:
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        # Keep this bounded: Celery creates a new loop per task, so without
        # eviction this dict would grow for the life of the worker.
        if len(_clients) > 8:
            _clients.clear()
        _clients[loop_id] = client
    return client


class GeminiTransientError(RuntimeError):
    """
    Raised on retryable upstream faults (429 rate limit, 503 high demand).
    Callers should let Celery retry rather than recording an empty result,
    which would silently lose data on a temporary blip.

    `retry_after` carries the delay Google asks for (its RetryInfo block),
    so the caller can honour it instead of guessing a fixed backoff and
    re-saturating the quota.
    """

    def __init__(self, message: str, retry_after: Optional[int] = None):
        super().__init__(message)
        self.retry_after = retry_after


class GeminiTruncatedError(RuntimeError):
    """
    Raised when the response hit the output-token ceiling.

    gemini-3.8-flash has thinking enabled by default and `max_output_tokens`
    is a SHARED budget covering thinking tokens *and* visible text. A trivial
    prompt burns ~90 thinking tokens; a real job description burns hundreds.
    The old 256/300-token budgets therefore returned either '' or *partial*
    JSON (e.g. '[\\n  "Python",\\n'), which json.loads rejected and the caller
    swallowed as "no skills found" — a total, invisible failure of enrichment.

    All extraction callers now pass thinking_budget=0, which removes the
    problem entirely. This error exists so that if a budget is ever exceeded
    again it fails loudly instead of degrading to empty output.
    """


class GeminiConfigError(RuntimeError):
    """
    Raised when Gemini fails for a reason that is a *deployment* problem
    rather than a per-item content problem: unknown/retired model ID,
    missing or invalid API key, permission denied, billing disabled.

    These must NOT be swallowed by the per-item `except Exception` handlers
    in skill_extractor / news_parser. Previously a retired model ID caused
    every call to 404 while the pipeline reported success — jobs simply came
    back with no skills and articles fell through to extractive summaries,
    with the real cause logged at DEBUG. This type is re-raised so the task
    fails loudly and visibly instead.
    """


# Substrings that identify a configuration fault rather than a content fault.
_CONFIG_FAULT_MARKERS = (
    "not found",
    "was not found",
    "is not supported",
    "api key not valid",
    "api_key_invalid",
    "permission denied",
    "permission_denied",
    "unauthenticated",
    "billing",
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


def _classify(exc: Exception) -> Exception:
    """Map an SDK exception onto our transient/config/other taxonomy."""
    text = f"{type(exc).__name__}: {exc}".lower()
    if any(marker in text for marker in _TRANSIENT_MARKERS):
        # Google returns e.g. 'retryDelay': '26s' on a quota error.
        match = re.search(r"'retryDelay':\s*'(\d+)s'", str(exc))
        retry_after = int(match.group(1)) if match else None
        return GeminiTransientError(
            f"Gemini temporarily unavailable: {exc}", retry_after=retry_after
        )
    if any(marker in text for marker in _CONFIG_FAULT_MARKERS):
        return GeminiConfigError(
            f"Gemini configuration fault (model={settings.GEMINI_MODEL!r}): {exc}"
        )
    return exc


async def verify_model() -> None:
    """
    Assert at startup that GEMINI_MODEL actually resolves.

    A wrong model ID otherwise fails invisibly on every call. Skipped when
    no API key is configured, so local dev without a key still boots.
    """
    if not settings.GEMINI_API_KEY:
        logger.warning(
            "GEMINI_API_KEY is empty — AI enrichment and news summarization "
            "will be skipped. Set it to enable them."
        )
        return
    try:
        await _get_client().aio.models.get(model=settings.GEMINI_MODEL)
        logger.info("Gemini model %r resolved OK", settings.GEMINI_MODEL)
    except Exception as exc:
        raise GeminiConfigError(
            f"GEMINI_MODEL={settings.GEMINI_MODEL!r} did not resolve: {exc}. "
            f"Check the model ID and that the API key has access to it."
        ) from exc


async def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.1,   # Low temp = more deterministic (good for extraction)
    max_tokens: int = 1024,
    thinking_budget: Optional[int] = 0,
) -> str:
    """
    Call Gemini for text generation using google-genai SDK v1.

    thinking_budget defaults to 0, which DISABLES thinking. Every current
    caller is a mechanical extraction task (skills -> JSON array, article ->
    JSON summary) where thinking adds cost and latency and buys nothing — and
    where leaving it on silently truncated the visible output (see
    GeminiTruncatedError). Pass None to use the model default, or a positive
    integer to cap it, if a genuinely reasoning-heavy caller is ever added.

    Raises:
        GeminiConfigError    — bad model ID / key / permissions (deployment fault)
        GeminiTransientError — 429 / 503 (retryable)
        GeminiTruncatedError — hit the output-token ceiling
    """
    config_kwargs = dict(
        system_instruction=system_instruction,
        temperature=temperature,
        max_output_tokens=max_tokens,
    )
    if thinking_budget is not None:
        config_kwargs["thinking_config"] = types.ThinkingConfig(
            thinking_budget=thinking_budget
        )

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

    # Truncation must not be reported as a successful empty/partial result.
    if finish_reason is not None and str(finish_reason).endswith("MAX_TOKENS"):
        thoughts = getattr(response.usage_metadata, "thoughts_token_count", None)
        raise GeminiTruncatedError(
            f"Response hit max_output_tokens={max_tokens} "
            f"(thinking_budget={thinking_budget}, thoughts_token_count={thoughts}). "
            f"Raise max_tokens or set thinking_budget=0."
        )
    if not text.strip():
        raise GeminiTruncatedError(
            f"Gemini returned empty text (finish_reason={finish_reason}, "
            f"max_tokens={max_tokens}, thinking_budget={thinking_budget})."
        )
    return text

# Enforced Output Schema via Pydantic
class ExtractedJobSchema(BaseModel):
    company_name: str = Field(description="The hiring company name")
    job_title: str = Field(description="Official job title")
    location: str = Field(description="Job location, e.g., 'Seattle, WA' or 'Remote'")
    is_remote: bool = Field(description="True if explicitly specified as remote")
    salary_min: Optional[int] = Field(default=None, description="Minimum annual compensation in USD")
    salary_max: Optional[int] = Field(default=None, description="Maximum annual compensation in USD")
    required_skills: List[str] = Field(description="List of primary technical skills/languages mentioned")

class StructuredGeminiExtractor:
    """
    Pre-processes HTML to reduce token usage and uses Gemini's
    Structured Outputs API for strict JSON parsing with google-genai SDK v1.
    """
    def __init__(self):
        self.client = _get_client()

    @staticmethod
    def clean_html_body(raw_html: str) -> str:
        """
        Strips script, style, nav, header, and footer tags from raw HTML
        to reduce token consumption by 60-80%.
        """
        soup = BeautifulSoup(raw_html, "html.parser")
        
        # Remove non-content tags
        for element in soup(["script", "style", "nav", "header", "footer", "noscript", "svg"]):
            element.decompose()
            
        # Extract readable text layout
        text = soup.get_text(separator="\n")
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        return "\n".join(lines)[:12000] # Cap character length for safety

    async def extract_job_details(self, raw_html: str) -> Optional[ExtractedJobSchema]:
        """
        Sends cleaned text context to Gemini and returns structured job data.
        """
        cleaned_text = self.clean_html_body(raw_html)
        
        prompt = (
            "Analyze the following job description text and extract structured job attributes. "
            "If a salary range is specified as hourly, convert it to an estimated annual base pay.\n\n"
            f"Job Description:\n{cleaned_text}"
        )

        try:
            # Request structured JSON output using Pydantic schema in google-genai v1
            response = await self.client.aio.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=ExtractedJobSchema,
                    temperature=0.1
                )
            )
            return response.parsed

        except Exception as e:
            logger.error(f"Failed structured extraction via Gemini API: {e}")
            return None