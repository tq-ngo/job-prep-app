import logging
from typing import Optional, List
from bs4 import BeautifulSoup
from pydantic import BaseModel, Field
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize client for google-genai v1 SDK
_client = genai.Client(api_key=settings.GEMINI_API_KEY)

async def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.1,   # Low temp = more deterministic (good for extraction)
    max_tokens: int = 1024,
) -> str:
    """
    Call Gemini for text generation using google-genai SDK v1.
    """
    response = await _client.aio.models.generate_content(
        model=settings.GEMINI_MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_tokens,
        )
    )
    return response.text

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
        self.client = _client

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