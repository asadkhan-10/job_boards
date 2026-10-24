"""enable pgvector

Revision ID: d4fb48b76381
Revises: 8b4f2e91c7a3
Create Date: 2026-10-24 13:02:16.113900

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4fb48b76381'
down_revision: Union[str, Sequence[str], None] = '8b4f2e91c7a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")