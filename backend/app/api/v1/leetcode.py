from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select
from datetime import date, timedelta
from app.core.database import get_session
from app.models.leetcode import LeetCodeSnapshot, LeetCodeSubmission
from app.services.ai_agent import GeminiAgentService
from typing import List

router = APIRouter()

@router.post("/submit", status_code=status.HTTP_201_CREATED, response_model=LeetCodeSubmission)
async def record_leetcode_submission(
    submission: LeetCodeSubmission,
    session: AsyncSession = Depends(get_session)
):
    ai_service = GeminiAgentService()
    
    try:
        # Await response analysis from the asynchronous Gemini implementation pipeline
        ai_evaluation = await ai_service.analyze_leetcode_performance(
            problem_title=submission.problem_name,
            submitted_code=submission.submission_code
        )
        
        # Map AI insights back to the model
        submission.next_review_due = date.today() + timedelta(
            days=ai_evaluation.recommended_spaced_repetition_days_interval
        )
        submission.execution_performance = ai_evaluation.optimization_strategy
        submission.conceptual_flaw = ai_evaluation.conceptual_flaw
        submission.time_complexity = ai_evaluation.optimal_time_complexity
        submission.space_complexity = ai_evaluation.optimal_space_complexity
        
        session.add(submission)
        await session.commit()
        await session.refresh(submission)
        
        return submission
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI analysis failed: {str(e)}"
        )

@router.get("/review-queue", response_model=List[LeetCodeSubmission])
async def get_spaced_repetition_queue(session: AsyncSession = Depends(get_session)):
    stmt = select(LeetCodeSubmission).where(LeetCodeSubmission.next_review_due <= date.today())
    result = await session.execute(stmt)
    return result.scalars().all()