"""add chunk_index and num_chunks to lab_doc

Revision ID: a1b2c3d4e5f7
Revises: b3c4d5e6f7a8
Create Date: 2026-04-07
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f7'
down_revision: Union[str, None] = 'b3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lab_doc', sa.Column('chunk_index', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('lab_doc', sa.Column('num_chunks', sa.Integer(), nullable=False, server_default='1'))


def downgrade() -> None:
    op.drop_column('lab_doc', 'num_chunks')
    op.drop_column('lab_doc', 'chunk_index')
