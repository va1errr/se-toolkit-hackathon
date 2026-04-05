"""Stats API endpoint: forum analytics."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import text

from app.database import get_session
from app.services.dependencies import get_current_user, User

router = APIRouter(prefix="/stats", tags=["stats"])


@router.get("")
async def get_stats(
    session: AsyncSession = Depends(get_session),
    _user: User = Depends(get_current_user),
):
    """Get forum analytics."""
    # Question counts by status
    status_counts = await session.execute(text("""
        SELECT status, COUNT(*) as count
        FROM question
        GROUP BY status
    """))
    status_data = {row.status: row.count for row in status_counts.fetchall()}

    # Total questions
    total_result = await session.execute(text("SELECT COUNT(*) FROM question"))
    total_questions = total_result.scalar() or 0

    # AI answer stats
    ai_result = await session.execute(text("""
        SELECT
            COUNT(*) as total_ai,
            AVG(confidence) as avg_confidence,
            COUNT(*) FILTER (WHERE confidence >= 0.5) as high_confidence,
            COUNT(*) FILTER (WHERE confidence < 0.5) as low_confidence,
            MIN(reasoning_time_seconds) as min_reasoning_time,
            MAX(reasoning_time_seconds) as max_reasoning_time,
            AVG(reasoning_time_seconds) as avg_reasoning_time
        FROM answer
        WHERE source = 'ai'
    """))
    ai_row = ai_result.first()

    # Rating stats
    rating_result = await session.execute(text("""
        SELECT
            COUNT(*) FILTER (WHERE helpful = true) as helpful,
            COUNT(*) FILTER (WHERE helpful = false) as not_helpful
        FROM rating
    """))
    rating_row = rating_result.first()

    # Users count
    users_result = await session.execute(text("SELECT COUNT(*) FROM \"user\""))
    total_users = users_result.scalar() or 0

    # TA count
    ta_result = await session.execute(text("SELECT COUNT(*) FROM \"user\" WHERE role IN ('ta', 'admin')"))
    total_tas = ta_result.scalar() or 0

    # Lab docs count
    labs_result = await session.execute(text("SELECT COUNT(*) FROM lab_doc"))
    total_labs = labs_result.scalar() or 0

    # Top 5 most active users (by questions posted)
    top_users = await session.execute(text("""
        SELECT u.username, u.role, COUNT(q.id) as question_count
        FROM "user" u
        LEFT JOIN question q ON q.user_id = u.id
        GROUP BY u.id
        ORDER BY question_count DESC
        LIMIT 5
    """))
    top_users_data = [
        {"username": row.username, "role": row.role, "questions": row.question_count}
        for row in top_users.fetchall()
    ]

    return {
        "total_questions": total_questions,
        "status_breakdown": status_data,
        "total_users": total_users,
        "total_tas": total_tas,
        "total_labs": total_labs,
        "ai_answers": ai_row.total_ai if ai_row else 0,
        "ai_avg_confidence": round(float(ai_row.avg_confidence), 2) if ai_row and ai_row.avg_confidence else 0,
        "ai_high_confidence": ai_row.high_confidence if ai_row else 0,
        "ai_low_confidence": ai_row.low_confidence if ai_row else 0,
        "ai_reasoning_time": {
            "min": round(float(ai_row.min_reasoning_time), 2) if ai_row and ai_row.min_reasoning_time else None,
            "max": round(float(ai_row.max_reasoning_time), 2) if ai_row and ai_row.max_reasoning_time else None,
            "avg": round(float(ai_row.avg_reasoning_time), 2) if ai_row and ai_row.avg_reasoning_time else None,
        },
        "ratings": {
            "helpful": rating_row.helpful if rating_row else 0,
            "not_helpful": rating_row.not_helpful if rating_row else 0,
        },
        "top_users": top_users_data,
    }
