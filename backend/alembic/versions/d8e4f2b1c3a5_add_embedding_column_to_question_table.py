"""add embedding column to question table for semantic search

Revision ID: d8e4f2b1c3a5
Revises: b7c3e1a9f2d4
Create Date: 2026-04-04 17:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector


# revision identifiers
revision: str = 'd8e4f2b1c3a5'
down_revision: Union[str, None] = 'b7c3e1a9f2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('question', sa.Column('embedding', Vector(384), nullable=True))


def downgrade() -> None:
    op.drop_column('question', 'embedding')
