"""Questions API endpoints: create, list, and get details."""

from uuid import UUID

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select

from app.database import get_session
from app.models.models import Answer, Question, User
from app.models.schemas import (
    AnswerResponse,
    QuestionCreate,
    QuestionDetail,
    QuestionResponse,
)
from app.services.dependencies import get_current_user
from app.services.rag import run_rag_pipeline

logger = structlog.get_logger()

router = APIRouter(prefix="/questions", tags=["questions"])


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(
    data: QuestionCreate,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new question. Triggers an AI answer via the RAG pipeline."""
    # 1. Create the question
    question = Question(
        user_id=current_user.id,
        title=data.title,
        body=data.body,
    )
    session.add(question)
    await session.flush()
    await session.refresh(question)

    # 2. Run RAG pipeline to generate AI answer
    try:
        answer_text, confidence, lab_numbers = await run_rag_pipeline(
            question_title=data.title,
            question_body=data.body,
            session=session,
        )

        # 3. Create the AI answer
        ai_answer = Answer(
            question_id=question.id,
            body=answer_text,
            source="ai",
            confidence=confidence,
        )
        session.add(ai_answer)
        await session.flush()

        # 4. Link the AI answer to the question
        question.ai_answer_id = ai_answer.id
        question.status = "answered" if confidence > 0.3 else "open"
        await session.flush()

        logger.info(
            "AI answer generated",
            question_id=str(question.id),
            confidence=confidence,
            labs=lab_numbers,
        )

    except Exception as e:
        logger.error("RAG pipeline failed for question", question_id=str(question.id), error=str(e))
        # Question stays in "open" status without an AI answer

    return question


@router.get("", response_model=list[QuestionResponse])
async def list_questions(
    status_filter: str | None = Query(None, alias="status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """List questions, optionally filtered by status. Paginated."""
    query = select(Question).order_by(Question.created_at.desc())
    if status_filter:
        query = query.where(Question.status == status_filter)
    query = query.offset(skip).limit(limit)

    result = await session.execute(query)
    return result.scalars().all()


@router.get("/{question_id}", response_model=QuestionDetail)
async def get_question(
    question_id: UUID,
    session: AsyncSession = Depends(get_session),
):
    """Get a question with all its answers."""
    result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Load answers
    answers_result = await session.execute(
        select(Answer).where(Answer.question_id == question_id).order_by(Answer.created_at)
    )
    answers = answers_result.scalars().all()

    # Build response dict manually to avoid ORM lazy-loading issues
    return {
        "id": question.id,
        "user_id": question.user_id,
        "title": question.title,
        "body": question.body,
        "status": question.status,
        "ai_answer_id": question.ai_answer_id,
        "created_at": question.created_at,
        "updated_at": question.updated_at,
        "answers": [
            {
                "id": a.id,
                "question_id": a.question_id,
                "user_id": a.user_id,
                "body": a.body,
                "source": a.source,
                "confidence": a.confidence,
                "created_at": a.created_at,
            }
            for a in answers
        ],
    }
