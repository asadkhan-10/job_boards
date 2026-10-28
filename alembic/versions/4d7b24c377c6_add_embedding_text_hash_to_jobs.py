"""add embedding_text_hash to jobs

Revision ID: 4d7b24c377c6
Revises: 653e41b96a90
Create Date: 2026-10-25 14:43:43.896477

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4d7b24c377c6'
down_revision: Union[str, Sequence[str], None] = '653e41b96a90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.add_column('jobs', sa.Column('embedding_text_hash', sa.String(length=64), nullable=True))

def downgrade() -> None:
    op.drop_column('jobs', 'embedding_text_hash')
