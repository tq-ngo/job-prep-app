from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
from app.core.config import settings

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
    MODEL = "gemini-3.5-flash"

    def __init__(self):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def analyze_leetcode_performance(
        self,
        problem_title: str,
        submitted_code: str,
        error_message: Optional[str] = None
    ) -> DSAReviewStructure:
        prompt = f"""
        Review this candidate's LeetCode submission.
        Problem: {problem_title}
        Code:
        ```python
        {submitted_code}
        ```
        Errors: {error_message or "None"}

        Provide DSA mentoring advice, time/space complexity analysis,
        spaced repetition interval (integer days), and structured follow-up questions.
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=DSAReviewStructure,
                    temperature=0.2
                ),
            )
            return response.parsed
        except Exception as e:
            print(f"Error calling Gemini for LeetCode: {e}")
            raise

    async def synthesize_market_news(self, raw_content: str) -> NewsSynthesis:
        prompt = f"""
        Analyze this raw technology market data and extract signals related to
        corporate health, hiring trends, and engineering innovations.
        
        Raw Content:
        {raw_content}
        """
        try:
            response = await self.client.aio.models.generate_content(
                model=self.MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=NewsSynthesis,
                    temperature=0.1
                ),
            )
            return response.parsed
        except Exception as e:
            print(f"Error calling Gemini for News: {e}")
            raise
