"""TA review endpoints: view flagged answers, add/edit/delete responses."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select, text

from app.database import get_session
from app.models.models import Answer, Question, Rating, User
from app.models.schemas import AnswerCreate, AnswerResponse
from app.services.dependencies import get_current_user, get_required_user, require_role

logger = structlog.get_logger()

router = APIRouter(prefix="/ta", tags=["ta-review"])


@router.get("/flagged")
async def get_flagged_answers(
    current_user: User = Depends(require_role("ta")),
    session: AsyncSession = Depends(get_session),
):
    """Get AI answers that need TA review:
    1. At least one 👎 rating on AI answer, OR
    2. AI answer with low confidence (status = 'open')

    Admins also see hidden questions (with `hidden: true`).
    A question is removed from the queue ONLY when a TA answer
    under that question gets at least one 👍.
    Returns questions ordered by most flagged first.
    """
    # Base query: AI answers with at least one 👎 OR open status
    base_query = text("""
        SELECT
            q.id as question_id,
            q.title,
            q.body,
            q.status,
            q.created_at as question_created,
            a.id as answer_id,
            a.body as answer_body,
            a.confidence,
            a.edited as ai_edited,
            q.hidden as is_hidden,
            a.created_at as answer_created,
            COUNT(CASE WHEN r.helpful = false THEN 1 END) as thumbs_down,
            COUNT(CASE WHEN r.helpful = true THEN 1 END) as thumbs_up
        FROM question q
        JOIN answer a ON a.id = q.ai_answer_id
        LEFT JOIN rating r ON r.answer_id = a.id
        WHERE a.source = 'ai'
        GROUP BY q.id, a.id
        HAVING COUNT(CASE WHEN r.helpful = false THEN 1 END) > 0
           OR q.status = 'open'
        ORDER BY thumbs_down DESC, q.created_at DESC
    """)

    result = await session.execute(base_query)
    rows = result.fetchall()

    flagged = []
    for row in rows:
        # Check if this question has a TA answer with ≥1 👍
        ta_likes_result = await session.execute(
            text("""
                SELECT COUNT(*) FROM answer ta
                JOIN rating tr ON tr.answer_id = ta.id
                WHERE ta.question_id = :qid
                AND ta.source != 'ai'
                AND tr.helpful = true
            """),
            {"qid": str(row.question_id)},
        )
        ta_likes_count = ta_likes_result.scalar()

        if ta_likes_count == 0:
            # For non-admins, skip hidden questions
            if row.is_hidden and current_user.role != "admin":
                continue

            flagged.append({
                "question_id": str(row.question_id),
                "title": row.title,
                "body": row.body,
                "status": row.status,
                "question_created": row.question_created.isoformat(),
                "ai_answer_id": str(row.answer_id),
                "ai_answer_body": row.answer_body,
                "ai_confidence": row.confidence,
                "ai_edited": row.ai_edited,
                "hidden": row.is_hidden,
                "answer_created": row.answer_created.isoformat(),
                "thumbs_down": row.thumbs_down,
                "thumbs_up": row.thumbs_up,
            })

    return flagged


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
    """TA adds a manual answer to a question."""
    q_result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = q_result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    ta_answer = Answer(
        question_id=question_id,
        user_id=ta_user.id,
        body=data.body,
        source="ta",
    )
    session.add(ta_answer)
    await session.commit()
    await session.refresh(ta_answer)

    logger.info(
        "TA added answer to question",
        question_id=str(question_id),
        ta_id=str(ta_user.id),
        answer_id=str(ta_answer.id),
    )

    return ta_answer


@router.put("/answers/{answer_id}", response_model=AnswerResponse)
async def edit_answer(
    answer_id: UUID,
    data: AnswerCreate,
    current_user: User = Depends(get_required_user),
    session: AsyncSession = Depends(get_session),
):
    """Edit an answer. TA can only edit own answers. Admin can edit any non-AI answer."""
    result = await session.execute(
        select(Answer).where(Answer.id == answer_id)
    )
    answer = result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.source == "ai":
        raise HTTPException(status_code=403, detail="AI answers cannot be edited")
    if current_user.role == "admin":
        pass  # Admin can edit any non-AI answer
    elif current_user.role == "ta" and answer.user_id == current_user.id:
        pass  # TA can edit own answers
    else:
        raise HTTPException(status_code=403, detail="You can only edit your own answers")

    answer.body = data.body
    answer.edited = True
    await session.commit()
    await session.refresh(answer)

    logger.info(
        "Answer edited",
        answer_id=str(answer_id),
        user_id=str(current_user.id),
        role=current_user.role,
    )

    return answer


@router.delete("/answers/{answer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_answer(
    answer_id: UUID,
    current_user: User = Depends(get_required_user),
    session: AsyncSession = Depends(get_session),
):
    """Delete an answer. TA can only delete own answers. Admin can delete any non-AI answer."""
    result = await session.execute(
        select(Answer).where(Answer.id == answer_id)
    )
    answer = result.scalar_one_or_none()
    if answer is None:
        raise HTTPException(status_code=404, detail="Answer not found")
    if answer.source == "ai":
        raise HTTPException(status_code=403, detail="AI answers cannot be deleted")
    if current_user.role == "admin":
        pass  # Admin can delete any non-AI answer
    elif current_user.role == "ta" and answer.user_id == current_user.id:
        pass  # TA can delete own answers
    else:
        raise HTTPException(status_code=403, detail="You can only delete your own answers")

    # Delete ratings for this answer first (FK constraint)
    await session.execute(
        text("DELETE FROM rating WHERE answer_id = :aid"),
        {"aid": str(answer_id)},
    )

    await session.delete(answer)
    await session.commit()

    logger.info(
        "Answer deleted",
        answer_id=str(answer_id),
        user_id=str(current_user.id),
        role=current_user.role,
    )


@router.put("/questions/{question_id}/hide", status_code=status.HTTP_204_NO_CONTENT)
async def hide_question(
    question_id: UUID,
    current_user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    """Admin hides a question from the TA queue (soft hide, not deletion)."""
    result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question.hidden = True
    await session.commit()

    logger.info(
        "Admin hid question from TA queue",
        question_id=str(question_id),
        admin_id=str(current_user.id),
    )


@router.put("/questions/{question_id}/unhide", status_code=status.HTTP_204_NO_CONTENT)
async def unhide_question(
    question_id: UUID,
    current_user: User = Depends(require_role("admin")),
    session: AsyncSession = Depends(get_session),
):
    """Admin unhides a question to show it in the TA queue again."""
    result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    question.hidden = False
    await session.commit()

    logger.info(
        "Admin unhid question in TA queue",
        question_id=str(question_id),
        admin_id=str(current_user.id),
    )
