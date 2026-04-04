"""SQLModel database models.

Each class below maps to one database table.
SQLModel handles both the Python model and the SQLAlchemy table definition.
"""

from typing import Optional, List
from datetime import datetime
from uuid import UUID, uuid4

from sqlmodel import SQLModel, Field, Relationship


class User(SQLModel, table=True):
    """Represents a user in the system (student, TA, or admin)."""

    __tablename__ = "user"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    username: str = Field(unique=True, index=True, max_length=50)
    password_hash: str = Field(max_length=255)
    role: str = Field(default="student")  # student / ta / admin
    created_at: datetime = Field(default_factory=datetime.utcnow)

    questions: List["Question"] = Relationship(back_populates="user")
    answers: List["Answer"] = Relationship(back_populates="user")
    ratings: List["Rating"] = Relationship(back_populates="user")


class Question(SQLModel, table=True):
    """A question posted by a student."""

    __tablename__ = "question"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="user.id")
    title: str = Field(max_length=200)
    body: str
    status: str = Field(default="open")  # open / answered / closed
    ai_answer_id: Optional[UUID] = Field(default=None, foreign_key="answer.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    user: User = Relationship(back_populates="questions")
    answers: List["Answer"] = Relationship(
        back_populates="question",
        sa_relationship_kwargs={"foreign_keys": "Answer.question_id"},
    )


class Answer(SQLModel, table=True):
    """An answer to a question — from AI, TA, or another student."""

    __tablename__ = "answer"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    question_id: UUID = Field(foreign_key="question.id")
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")  # NULL for AI
    body: str
    source: str  # ai / ta / student
    confidence: Optional[float] = Field(default=None, ge=0, le=1)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    question: Question = Relationship(
        back_populates="answers",
        sa_relationship_kwargs={"foreign_keys": "Answer.question_id"},
    )
    user: Optional[User] = Relationship(back_populates="answers")
    ratings: List["Rating"] = Relationship(
        back_populates="answer",
        sa_relationship_kwargs={"foreign_keys": "Rating.answer_id"},
    )


class Rating(SQLModel, table=True):
    """A thumbs-up/thumbs-down rating on an answer."""

    __tablename__ = "rating"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    answer_id: UUID = Field(foreign_key="answer.id")
    user_id: UUID = Field(foreign_key="user.id")
    helpful: bool
    created_at: datetime = Field(default_factory=datetime.utcnow)

    answer: Answer = Relationship(
        back_populates="ratings",
        sa_relationship_kwargs={"foreign_keys": "Rating.answer_id"},
    )
    user: User = Relationship(back_populates="ratings")


class LabDoc(SQLModel, table=True):
    """A lab document used by the RAG pipeline for context retrieval."""

    __tablename__ = "lab_doc"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    lab_number: int
    title: str
    content: str
    updated_at: datetime = Field(default_factory=datetime.utcnow)
