"""add edited column to answer table

Revision ID: e9f5a3b2d4c6
Revises: d8e4f2b1c3a5
Create Date: 2026-04-04 18:00:00
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = 'e9f5a3b2d4c6'
down_revision: Union[str, None] = 'd8e4f2b1c3a5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('answer', sa.Column('edited', sa.Boolean(), nullable=False, server_default='false'))


def downgrade() -> None:
    op.drop_column('answer', 'edited')
