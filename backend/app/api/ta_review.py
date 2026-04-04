"""TA review endpoints: view flagged answers and add manual responses."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select, text

from app.database import get_session
from app.models.models import Answer, Question, Rating, User
from app.models.schemas import AnswerCreate, AnswerResponse
from app.services.dependencies import require_role

logger = structlog.get_logger()

router = APIRouter(prefix="/ta", tags=["ta-review"])


@router.get("/flagged")
async def get_flagged_answers(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(require_role("ta")),
):
    """Get all questions with at least one 👎 rating on their AI answer.

    Returns questions ordered by most flagged first.
    """
    query = text("""
        SELECT
            q.id as question_id,
            q.title,
            q.body,
            q.status,
            q.created_at as question_created,
            a.id as answer_id,
            a.body as answer_body,
            a.confidence,
            a.created_at as answer_created,
            COUNT(CASE WHEN r.helpful = false THEN 1 END) as thumbs_down,
            COUNT(CASE WHEN r.helpful = true THEN 1 END) as thumbs_up
        FROM question q
        JOIN answer a ON a.id = q.ai_answer_id
        LEFT JOIN rating r ON r.answer_id = a.id
        WHERE a.source = 'ai'
        GROUP BY q.id, a.id
        HAVING COUNT(CASE WHEN r.helpful = false THEN 1 END) > 0
        ORDER BY thumbs_down DESC, q.created_at DESC
    """)

    result = await session.execute(query)
    rows = result.fetchall()

    return [
        {
            "question_id": str(row.question_id),
            "title": row.title,
            "body": row.body,
            "status": row.status,
            "question_created": row.question_created.isoformat(),
            "ai_answer_id": str(row.answer_id),
            "ai_answer_body": row.answer_body,
            "ai_confidence": row.confidence,
            "answer_created": row.answer_created.isoformat(),
            "thumbs_down": row.thumbs_down,
            "thumbs_up": row.thumbs_up,
        }
        for row in rows
    ]


@router.post(
    "/questions/{question_id}/answer",
    response_model=AnswerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ta_add_answer(
    question_id: UUID,
    data: AnswerCreate,
    ta_user: User = Depends(require_role("ta")),
    session: AsyncSession = Depends(get_session),
):
    """TA adds a manual answer to a question (usually to correct a bad AI answer)."""
    # Verify question exists
    q_result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Create TA answer
    ta_answer = Answer(
        question_id=question_id,
        user_id=ta_user.id,
        body=data.body,
        source="ta",
    )
    session.add(ta_answer)
    await session.flush()

    # Update question: mark as answered, link TA answer as primary
    question.status = "answered"
    # Keep original AI answer but TA answer is now also visible
    await session.commit()
    await session.refresh(ta_answer)

    logger.info(
        "TA added answer to question",
        question_id=str(question_id),
        ta_id=str(ta_user.id),
        answer_id=str(ta_answer.id),
    )

    return ta_answer
