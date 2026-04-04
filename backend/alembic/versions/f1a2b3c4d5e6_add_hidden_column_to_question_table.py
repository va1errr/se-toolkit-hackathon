"""add hidden column to question table

Revision ID: f1a2b3c4d5e6
Revises: e9f5a3b2d4c6
Create Date: 2026-04-04 19:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'e9f5a3b2d4c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('question', sa.Column('hidden', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('question', 'hidden')
