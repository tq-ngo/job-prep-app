import logging
import math
from google.genai import types
from app.config import settings
from app.ai.gemini_client import _classify, _get_client

logger = logging.getLogger(__name__)


def _l2_normalize(values: list[float]) -> list[float]:
    """L2-normalize a truncated Matryoshka embedding for cosine similarity."""
    norm = math.sqrt(sum(v * v for v in values))
    if norm <= 0.0:
        return list(values)
    return [v / norm for v in values]


async def generate_embedding(text: str, task_type: str = "RETRIEVAL_DOCUMENT") -> list[float]:
    """
    Generate a 768-dimensional L2-normalized text embedding using
    settings.EMBEDDING_MODEL (default: gemini-embedding-001).

    `output_dimensionality` is pinned to settings.EMBEDDING_DIMENSIONS (768)
    so vectors match the PostgreSQL pgvector `Vector(768)` column even on
    models whose native output is 3072-dim. Truncated embeddings are
    L2-normalized per Google's embedding documentation.

    `task_type` is RETRIEVAL_DOCUMENT for indexed jobs and RETRIEVAL_QUERY
    for search queries.
    """
    dims = settings.EMBEDDING_DIMENSIONS
    try:
        response = await _get_client().aio.models.embed_content(
            model=settings.EMBEDDING_MODEL,
            contents=text[:8000],  # Model has an input token limit
            config=types.EmbedContentConfig(
                task_type=task_type,
                output_dimensionality=dims,
            ),
        )
    except Exception as exc:
        raise _classify(exc) from exc
    values = list(response.embeddings[0].values)
    if len(values) != dims:
        raise RuntimeError(
            f"Expected {dims}-dim embedding from {settings.EMBEDDING_MODEL!r}, got {len(values)}"
        )
    return _l2_normalize(values)
