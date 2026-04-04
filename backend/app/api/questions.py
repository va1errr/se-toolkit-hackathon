"""Questions API endpoints: create, list, and get details."""

from typing import Optional
from uuid import UUID

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import col, select, text

from app.database import get_session
from app.models.models import Answer, Question, User
from app.models.schemas import (
    AnswerResponse,
    QuestionCreate,
    QuestionDetail,
    QuestionResponse,
)
from app.services.dependencies import get_current_user, get_required_user
from app.services.rag import run_rag_pipeline
from app.services.embeddings import embed_text

logger = structlog.get_logger()

router = APIRouter(prefix="/questions", tags=["questions"])


async def _generate_ai_answer(question_id_str: str, title: str, body: str):
    """Background task to generate AI answer and embed question after creation."""
    from sqlalchemy.ext.asyncio import AsyncSession as BGAsyncSession, create_async_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import settings
    from app.models.models import Answer, Question

    engine = create_async_engine(settings.database_url)
    AsyncSessionLocal = sessionmaker(bind=engine, class_=BGAsyncSession, expire_on_commit=False)

    async with AsyncSessionLocal() as session:
        try:
            # Embed the question for future semantic search
            question_embedding = embed_text(f"{title}\n\n{body}")

            # Run RAG pipeline
            answer_text, confidence, lab_numbers = await run_rag_pipeline(
                question_title=title,
                question_body=body,
                session=session,
            )

            ai_answer = Answer(
                question_id=question_id_str,
                body=answer_text,
                source="ai",
                confidence=confidence,
            )
            session.add(ai_answer)
            await session.flush()

            # Update question with embedding and AI answer
            result = await session.execute(
                select(Question).where(Question.id == question_id_str)
            )
            question = result.scalar_one()
            question.embedding = question_embedding
            question.ai_answer_id = ai_answer.id
            question.status = "answered" if confidence > 0.3 else "open"
            await session.commit()

            logger.info(
                "Background AI answer generated",
                question_id=question_id_str,
                confidence=confidence,
                labs=lab_numbers,
            )
        except Exception as e:
            logger.error("Background RAG failed", question_id=question_id_str, error=str(e))
            # Leave question as "open" without AI answer
        finally:
            await engine.dispose()


@router.post(
    "",
    response_model=QuestionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_question(
    data: QuestionCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_required_user),
    session: AsyncSession = Depends(get_session),
):
    """Create a new question. AI answer is generated in the background."""
    # 1. Create the question immediately
    question = Question(
        user_id=current_user.id,
        title=data.title,
        body=data.body,
        status="analyzing",
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)

    # 2. Schedule RAG pipeline to run after response is sent
    background_tasks.add_task(
        _generate_ai_answer,
        str(question.id),
        data.title,
        data.body,
    )

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


@router.get("/search")
async def search_questions(
    q: str = Query(..., min_length=3),
    top_k: int = Query(5, ge=1, le=20),
    session: AsyncSession = Depends(get_session),
):
    """Search for semantically similar questions using pgvector.

    Embeds the query text and finds the most similar existing questions.
    Used to suggest existing questions before the user posts a duplicate.
    """
    query_embedding = embed_text(q)
    embedding_str = str(query_embedding)

    result = await session.execute(
        text("""
            SELECT id, user_id, title, body, status, ai_answer_id,
                   created_at, updated_at,
                   1 - (embedding <=> CAST(:emb AS vector)) AS similarity
            FROM question
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> CAST(:emb AS vector)
            LIMIT :limit
        """),
        {"emb": embedding_str, "limit": top_k},
    )
    rows = result.fetchall()

    return [
        {
            "id": str(row.id),
            "user_id": str(row.user_id),
            "title": row.title,
            "body": row.body,
            "status": row.status,
            "ai_answer_id": str(row.ai_answer_id) if row.ai_answer_id else None,
            "created_at": row.created_at.isoformat(),
            "updated_at": row.updated_at.isoformat(),
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


@router.get("/{question_id}", response_model=QuestionDetail)
async def get_question(
    question_id: UUID,
    current_user: Optional[User] = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """Get a question with all its answers."""
    # Handle auth being optional (unauthenticated users can still view)
    current_user_id = str(current_user.id) if current_user else None
    result = await session.execute(
        select(Question).where(Question.id == question_id)
    )
    question = result.scalar_one_or_none()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    # Load answers with their rating counts
    answers_result = await session.execute(
        select(Answer).where(Answer.question_id == question_id).order_by(Answer.created_at)
    )
    answers = answers_result.scalars().all()

    # Count ratings per answer and check if current user rated
    ratings_by_answer = {}
    for a in answers:
        answer_id = str(a.id)

        # Get counts
        rating_counts = await session.execute(
            text("""
                SELECT
                    SUM(CASE WHEN helpful THEN 1 ELSE 0 END) AS helpful_count,
                    SUM(CASE WHEN NOT helpful THEN 1 ELSE 0 END) AS not_helpful_count
                FROM rating
                WHERE answer_id = :aid
            """),
            {"aid": answer_id},
        )
        row = rating_counts.first()

        # Get current user's own rating (if logged in)
        user_rating = None
        if current_user_id:
            user_rating_result = await session.execute(
                text("""
                    SELECT helpful FROM rating
                    WHERE answer_id = :aid AND user_id = :uid
                    LIMIT 1
                """),
                {"aid": answer_id, "uid": current_user_id},
            )
            user_rating_row = user_rating_result.first()
            if user_rating_row:
                user_rating = user_rating_row.helpful

        ratings_by_answer[answer_id] = {
            "helpful_count": int(row.helpful_count or 0),
            "not_helpful_count": int(row.not_helpful_count or 0),
            "user_rating": user_rating,
        }

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
                "edited": a.edited,
                "helpful_count": ratings_by_answer[str(a.id)]["helpful_count"],
                "not_helpful_count": ratings_by_answer[str(a.id)]["not_helpful_count"],
                "user_rating": ratings_by_answer[str(a.id)]["user_rating"],
            }
            for a in answers
        ],
    }
