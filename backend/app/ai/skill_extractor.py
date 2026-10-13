import logging
from typing import List, Optional

from pydantic import BaseModel, Field, ValidationError

from app.ai.gemini_client import (
    generate_structured,
    GeminiConfigError,
    GeminiTransientError,
    GeminiTruncatedError,
)

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You extract structured attributes from software job postings.

Skills:
1. Only technical skills: programming languages, frameworks, tools, platforms.
2. Normalize names: "JS" -> "JavaScript", "Py" -> "Python", "k8s" -> "Kubernetes".
3. No soft skills ("communication", "teamwork") and no phrases
   ("experience with X") — just the skill name. At most 20.

Compensation: only if the posting states a number. Report it in the period
the posting uses — do NOT convert hourly pay to annual. Use whole USD; if a
single figure is given, set both min and max to it. Otherwise leave null.

Seniority: one of intern, new_grad, junior, mid, senior, staff, or null.
Employment type: one of internship, co_op, full_time, part_time, contract, or null.
"""

SENIORITY_LEVELS = {"intern", "new_grad", "junior", "mid", "senior", "staff"}
EMPLOYMENT_TYPES = {"internship", "co_op", "full_time", "part_time", "contract"}
SALARY_PERIODS = {"hour", "year"}


class JobAttributes(BaseModel):
    skills: List[str] = Field(default_factory=list, description="Normalized technical skills, max 20")
    salary_min: Optional[int] = Field(default=None, description="Lowest stated pay, whole USD")
    salary_max: Optional[int] = Field(default=None, description="Highest stated pay, whole USD")
    salary_period: Optional[str] = Field(default=None, description='"hour" or "year"')
    seniority_level: Optional[str] = Field(default=None, description="intern|new_grad|junior|mid|senior|staff")
    employment_type: Optional[str] = Field(default=None, description="internship|co_op|full_time|part_time|contract")

    def normalized(self) -> "JobAttributes":
        """Drop values outside the allowed vocabularies or that make no sense."""
        by_key: dict = {}
        for raw in self.skills:
            name = (raw or "").strip()
            if name:
                by_key.setdefault(name.lower(), name)  # case-insensitive dedupe
        skills = sorted(by_key.values(), key=str.lower)[:20]
        period = self.salary_period if self.salary_period in SALARY_PERIODS else None
        lo, hi = self.salary_min, self.salary_max
        if lo is not None and lo <= 0:
            lo = None
        if hi is not None and hi <= 0:
            hi = None
        if lo and hi and lo > hi:
            lo, hi = hi, lo
        if (lo or hi) and period is None:
            lo = hi = None  # a number without a period is uninterpretable
        return JobAttributes(
            skills=skills,
            salary_min=lo,
            salary_max=hi,
            salary_period=period if (lo or hi) else None,
            seniority_level=self.seniority_level if self.seniority_level in SENIORITY_LEVELS else None,
            employment_type=self.employment_type if self.employment_type in EMPLOYMENT_TYPES else None,
        )


async def extract_job_attributes(job_title: str, job_description: str) -> JobAttributes:
    """
    One structured Gemini call per job: skills, pay, seniority, and
    employment type.

    Replaces a free-text "return ONLY a JSON array" skills prompt parsed with
    regex. Using a response schema removes the parsing step, and folding in
    the other attributes fills salary/seniority/employment columns that
    existed on the model but were never populated — at no extra request.
    """
    prompt = f"Job Title: {job_title}\n\nJob Description:\n{job_description[:6000]}"
    try:
        attrs = await generate_structured(
            prompt=prompt, schema=JobAttributes, system_instruction=SYSTEM_PROMPT
        )
        return attrs.normalized()
    except (GeminiConfigError, GeminiTransientError, GeminiTruncatedError):
        # Deployment fault, retryable upstream blip, or truncated output.
        # None of these mean "this job has nothing to extract", so propagate
        # and let the Celery task retry/fail visibly.
        raise
    except ValidationError as exc:
        logger.error("Job attribute extraction returned off-schema JSON: %s", exc)
        return JobAttributes()
