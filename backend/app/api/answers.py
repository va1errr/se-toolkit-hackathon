"""Answers and Ratings API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.database import get_session
from app.models.models import Answer, Rating, Question, User
from app.models.schemas import (
    AnswerCreate,
    AnswerResponse,
    RatingCreate,
    RatingResponse,
)
from app.services.dependencies import get_current_user, require_role

router = APIRouter(tags=["answers", "ratings"])


# ===================== Answers =====================

@router.post(
    "/questions/{question_id}/answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_answer(
    question_id: UUID,
    data: AnswerCreate,
    current_user: User = Depends(require_role("ta")),
    session: AsyncSession = Depends(get_session),
):
    """Add a manual answer to a question (TA only)."""
    # Verify question exists
    q_result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    answer = Answer(
        question_id=question_id,
        user_id=current_user.id,
        body=data.body,
        source="ta",
    )
    session.add(answer)
    await session.flush()
    await session.refresh(answer)

    return answer


# ===================== Ratings =====================

@router.post(
    "/answers/{answer_id}/rate",
    response_model=RatingResponse,
    status_code=status.HTTP_201_CREATED,
)
async def rate_answer(
    answer_id: UUID,
    data: RatingCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Rate an answer as helpful or not (students only)."""
    # Verify answer exists
    a_result = await session.execute(
        select(Answer).where(Answer.id == answer_id)
    )
    answer = a_result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(status_code=404, detail="Answer not found")

    # Check if user already rated this answer
    existing = await session.execute(
        select(Rating).where(
            Rating.answer_id == answer_id,
            Rating.user_id == current_user.id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="You have already rated this answer",
        )

    rating = Rating(
        answer_id=answer_id,
        user_id=current_user.id,
        helpful=data.helpful,
    )
    session.add(rating)
    await session.flush()
    await session.refresh(rating)

    return rating
