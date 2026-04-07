"""Answers and Ratings API endpoints."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, text

from app.database import get_session
from app.models.models import Answer, Rating, Question, User
from app.models.schemas import (
    AnswerCreate,
    AnswerResponse,
    RatingCreate,
    RatingResponse,
)
from app.services.dependencies import get_current_user, get_required_user, require_role

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
    current_user: User = Depends(get_required_user),
    session: AsyncSession = Depends(get_session),
):
    """Rate an answer as helpful or not."""
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
    existing_rating = existing.scalar_one_or_none()

    if existing_rating:
        # User already rated — update their choice
        existing_rating.helpful = data.helpful
        await session.flush()
        await session.refresh(existing_rating)
        rating = existing_rating
    else:
        rating = Rating(
            answer_id=answer_id,
            user_id=current_user.id,
            helpful=data.helpful,
        )
        session.add(rating)
        await session.flush()
        await session.refresh(rating)

    # If a non-AI answer gets its first 👍, mark question as answered (remove from queue)
    if data.helpful and answer.source != "ai":
        like_count = await session.execute(
            text("SELECT COUNT(*) FROM rating WHERE answer_id = :aid AND helpful = true"),
            {"aid": str(answer_id)},
        )
        if like_count.scalar() >= 1:
            await session.execute(
                text("UPDATE question SET status = 'answered' WHERE id = :qid"),
                {"qid": str(answer.question_id)},
            )
            await session.commit()

    # If a non-AI answer lost its last 👍, check if question should go back to open
    if not data.helpful and answer.source != "ai":
        # Check if there's still a TA answer with ≥1 like for this question
        ta_likes_result = await session.execute(
            text("""
                SELECT COUNT(*) FROM rating r
                JOIN answer ta ON ta.id = r.answer_id
                WHERE ta.question_id = :qid AND ta.source != 'ai' AND r.helpful = true
            """),
            {"qid": str(answer.question_id)},
        )
        if ta_likes_result.scalar() == 0:
            # No TA answer has likes anymore — put back in queue
            await session.execute(
                text("UPDATE question SET status = 'open' WHERE id = :qid"),
                {"qid": str(answer.question_id)},
            )
            await session.commit()

    return rating
