"""Pydantic schemas for API request validation and response serialization.

These are separate from SQLModel database models.
SQLModel models define database tables; these schemas define what the API accepts and returns.
"""

from datetime import datetime
from uuid import UUID
from typing import Optional

from pydantic import BaseModel


# ===================== Auth =====================

class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "student"


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ===================== User =====================

class UserResponse(BaseModel):
    id: UUID
    username: str
    role: str
    created_at: datetime

    class ConfigDict:  # noqa: N801
        from_attributes = True


# ===================== Questions =====================

class QuestionCreate(BaseModel):
    title: str
    body: str


class QuestionResponse(BaseModel):
    id: UUID
    user_id: UUID
    title: str
    body: str
    status: str
    ai_answer_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime

    class ConfigDict:  # noqa: N801
        from_attributes = True


class QuestionDetail(QuestionResponse):
    answers: list["AnswerResponse"] = []


# ===================== Answers =====================

class AnswerCreate(BaseModel):
    body: str


class AnswerResponse(BaseModel):
    id: UUID
    question_id: UUID
    user_id: Optional[UUID] = None
    body: str
    source: str
    confidence: Optional[float] = None
    created_at: datetime
    edited: bool = False
    helpful_count: int = 0
    not_helpful_count: int = 0
    reasoning_time_seconds: Optional[float] = None

    class ConfigDict:  # noqa: N801
        from_attributes = True


# ===================== Ratings =====================

class RatingCreate(BaseModel):
    helpful: bool


class RatingResponse(BaseModel):
    id: UUID
    answer_id: UUID
    user_id: UUID
    helpful: bool
    created_at: datetime

    class ConfigDict:  # noqa: N801
        from_attributes = True


# Resolve forward reference (QuestionDetail references AnswerResponse)
QuestionDetail.model_rebuild()
