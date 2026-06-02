from datetime import date, datetime
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship
from typing import List, Optional

class LeetCodeSnapshot(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    log_date: date = Field(default_factory=date.today, index=True)
    problems_solved: int = Field(default=0)
    easy_solved: int = Field(default=0)
    medium_solved: int = Field(default=0)
    hard_solved: int = Field(default=0)
    
    user_id: UUID = Field(foreign_key="user.id")
    user: "User" = Relationship(back_populates="leetcode_stats")

class LeetCodeSubmission(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    problem_name: str = Field(index=True)
    submission_code: str
    language: str = Field(default="python")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # AI Insights & Spaced Repetition
    next_review_due: date = Field(default_factory=date.today, index=True)
    execution_performance: Optional[str] = None # Optimization strategy from AI
    conceptual_flaw: Optional[str] = None
    time_complexity: Optional[str] = None
    space_complexity: Optional[str] = None
    
    user_id: UUID = Field(foreign_key="user.id")
    user: "User" = Relationship(back_populates="leetcode_submissions")