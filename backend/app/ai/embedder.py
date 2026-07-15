import logging
from google import genai
from app.config import settings

logger = logging.getLogger(__name__)
_client = genai.Client(api_key=settings.GEMINI_API_KEY)


async def generate_embedding(text: str) -> list[float]:
    """
    Generate a 768-dimensional text embedding using text-embedding-004.
    
    What is an embedding?
    A vector is a list of numbers that represents the "meaning" of text
    in a high-dimensional space. Two pieces of text with similar meaning
    will have vectors that are close together (high cosine similarity).
    
    This is what powers "find jobs similar to my resume":
    1. Embed the user's resume
    2. Find job embeddings nearest to the resume embedding
    3. Those are the most semantically relevant jobs
    
    text-embedding-004 produces 768-dimensional vectors.
    (768 floats × 4 bytes each = ~3KB per embedding)
    """
    response = await _client.aio.models.embed_content(
        model=settings.EMBEDDING_MODEL,
        contents=text[:8000],  # Model has an input token limit
        config={
            "task_type": "RETRIEVAL_DOCUMENT",  # Optimized for search
        }
    )
    return response.embeddings[0].values