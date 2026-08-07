import logging
from typing import List, Optional
from pydantic import BaseModel
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

class DSAReviewStructure(BaseModel):
    conceptual_flaw: str
    optimal_time_complexity: str
    optimal_space_complexity: str
    optimization_strategy: str
    recommended_drills: List[str]
    recommended_spaced_repetition_days_interval: int
    follow_up_interview_questions: List[str]

class NewsSynthesis(BaseModel):
    summary: str
    impact_level: str        # High, Medium, Low
    hiring_sentiment: str    # Hiring, Layoffs, Neutral
    key_takeaways: List[str]

class GeminiAgentService:
    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model = settings.GEMINI_MODEL

    async def synthesize_market_news(self, raw_content: str) -> Optional[NewsSynthesis]:
        prompt = f"""
        Analyze this raw technology market data and extract signals related to
        corporate health, hiring trends, and engineering innovations.
        
        Raw Content:
        {raw_content}
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=NewsSynthesis,
                    temperature=0.1
                ),
            )
            return response.parsed
        except Exception as e:
            logger.error(f"Error calling Gemini for News: {e}")
            return None
