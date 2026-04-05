"""add ai_reasoning_time_seconds to question table

Revision ID: b3c4d5e6f7a8
Revises: a2b3c4d5e6f7
Create Date: 2026-04-05 13:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'b3c4d5e6f7a8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('question', sa.Column('ai_reasoning_time_seconds', sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column('question', 'ai_reasoning_time_seconds')
