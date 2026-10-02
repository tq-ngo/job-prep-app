import json
import logging
import re
from app.ai.gemini_client import (
    generate_text,
    GeminiConfigError,
    GeminiTransientError,
    GeminiTruncatedError,
)

logger = logging.getLogger(__name__)

SKILL_EXTRACTION_SYSTEM_PROMPT = """
You are a technical skill extractor for job listings. Your job is to extract
a clean, normalized list of technical skills from job descriptions.

Rules:
1. Extract only technical skills (programming languages, frameworks, tools, platforms)
2. Normalize names: "JS" → "JavaScript", "Py" → "Python", "k8s" → "Kubernetes"
3. Do NOT include soft skills ("communication", "teamwork")
4. Do NOT include vague terms ("experience with X", "knowledge of Y") — just the skill name
5. Return a JSON array of strings, nothing else
6. Maximum 20 skills
7. Sort alphabetically

Example output: ["Docker", "FastAPI", "Kubernetes", "PostgreSQL", "Python", "Redis"]
"""


async def extract_skills(job_title: str, job_description: str) -> list[str]:
    """
    Use Gemini to extract technical skills from a job posting.
    
    We use a structured prompt that instructs Gemini to return JSON.
    Then we parse the JSON response.
    
    Why not use a fixed keyword list?
    Because job descriptions are inconsistent. 
    "postgres", "PostgreSQL", "PSQL" all mean the same thing.
    Gemini handles this normalization automatically.
    """
    prompt = f"""
Job Title: {job_title}

Job Description:
{job_description[:3000]}

Extract all technical skills from this job posting.
Return ONLY a JSON array of strings. No explanation, no markdown, no backticks.
"""
    
    try:
        response_text = await generate_text(
            prompt=prompt,
            system_instruction=SKILL_EXTRACTION_SYSTEM_PROMPT,
            temperature=0.0,    # Fully deterministic
            max_tokens=1024,
        )
        
        # Clean up the response (sometimes Gemini wraps in ```json ... ```)
        clean = response_text.strip()
        clean = re.sub(r'^```json\s*', '', clean)
        clean = re.sub(r'\s*```$', '', clean)
        
        skills = json.loads(clean)
        
        if isinstance(skills, list):
            # Validate each item is a string
            return [str(s) for s in skills if s]
        
        return []
        
    except (GeminiConfigError, GeminiTransientError, GeminiTruncatedError):
        # Deployment fault, retryable upstream blip, or a truncated response.
        # None of these mean "this job has no skills", so propagate and let
        # the Celery task retry/fail visibly. Returning [] here is what made
        # a total Gemini outage look like successful enrichment.
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Skill extraction: failed to parse JSON: {e}\nResponse: {response_text}")
        return []
    except Exception as e:
        logger.error(f"Skill extraction failed: {e}")
        return []