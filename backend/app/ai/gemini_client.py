import logging
from google import genai
from google.genai import types
from app.config import settings

logger = logging.getLogger(__name__)

# Initialize the client once
# google-genai v1.x+ uses this client pattern
_client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def generate_text(
    prompt: str,
    system_instruction: str = "",
    temperature: float = 0.1,   # Low temp = more deterministic (good for extraction)
    max_tokens: int = 1024,
) -> str:
    """
    Call Gemini for text generation.
    
    temperature:
    - 0.0: Fully deterministic, same input → same output always
    - 0.1: Near-deterministic (good for structured extraction)
    - 0.7: Creative (good for summaries, writing)
    - 1.0: Very creative / random
    
    We use low temperature for skill extraction (we want the same
    skills extracted consistently) and higher for article summaries.
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