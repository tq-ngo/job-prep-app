import logging
from google import genai
from app.config import settings

logger = logging.getLogger(__name__)
# Reuse the shared per-event-loop client. A module-level genai.Client binds
# its async transport to the first event loop that touches it, and Celery's
# async_to_sync creates a new loop per task -> "Event loop is closed" on the
# second and every later task.
from app.ai.gemini_client import _classify, _get_client


async def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
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

    `task_type` is RETRIEVAL_DOCUMENT for the jobs being indexed and
    RETRIEVAL_QUERY for a search query matched against them; the model
    embeds the two sides asymmetrically.

    SDK errors are mapped onto the Gemini error taxonomy, so a 429 surfaces
    as GeminiTransientError (with Google's retry delay) and a bad key as
    GeminiConfigError, the same as the generation calls.
    """
    try:
        response = await _get_client().aio.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text[:8000],  # Model has an input token limit
            config={"task_type": task_type},
        )
    except Exception as exc:
        raise _classify(exc) from exc
    return response.embeddings[0].values