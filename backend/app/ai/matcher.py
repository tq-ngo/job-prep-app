from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from app.models.job import Job


async def find_similar_jobs(
    query_text: str,
    session: AsyncSession,
    top_k: int = 10,
    min_similarity: float = 0.7,
) -> list[tuple[Job, float]]:
    """
    Find jobs semantically similar to the query text.
    
    Uses pgvector's cosine similarity operator (<=>).
    
    How pgvector works:
    - Stores embeddings as native vector columns
    - Creates an IVFFlat index for approximate nearest neighbor search
    - <=> operator = cosine distance (0 = identical, 2 = opposite)
    - Cosine similarity = 1 - cosine distance
    
    Example query: "I have 3 years of Python experience with FastAPI and Docker"
    → Embeds the query
    → Searches for jobs with nearest embeddings
    → Returns "Senior Python Engineer", "FastAPI Developer", etc.
    
    Returns: List of (Job, similarity_score) tuples sorted by similarity desc
    """
    from app.ai.embedder import generate_embedding
    
    query_embedding = await generate_embedding(query_text)
    
    # pgvector SQL:
    # embedding <=> '[...]' = cosine distance between stored vector and query
    # We sort ascending (smallest distance = most similar)
    # 1 - distance = similarity score (0 to 1)
    result = await session.execute(
        text("""
            SELECT 
                id,
                1 - (embedding <=> :query_vec::vector) AS similarity
            FROM jobs
            WHERE 
                embedding IS NOT NULL
                AND is_active = true
                AND 1 - (embedding <=> :query_vec::vector) >= :min_sim
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :top_k
        """),
        {
            "query_vec": str(query_embedding),
            "min_sim": min_similarity,
            "top_k": top_k,
        }
    )
    
    rows = result.fetchall()
    job_ids = [row.id for row in rows]
    similarities = {row.id: row.similarity for row in rows}
    
    # Fetch full job objects
    jobs_result = await session.execute(
        text("SELECT * FROM jobs WHERE id = ANY(:ids)"),
        {"ids": job_ids}
    )
    
    # Note: We'd need to map rows to Job objects properly in production
    # This is simplified for clarity
    return [(job, similarities[job.id]) for job in jobs_result.scalars()]