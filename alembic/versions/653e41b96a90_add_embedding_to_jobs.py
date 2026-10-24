"""add embedding to jobs

Revision ID: 653e41b96a90
Revises: d4fb48b76381
Create Date: 2026-10-24 13:58:03.287398

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '653e41b96a90'
down_revision: Union[str, Sequence[str], None] = 'd4fb48b76381'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

def upgrade() -> None:
    op.execute("ALTER TABLE jobs ADD COLUMN embedding vector(1024)")

def downgrade() -> None:
    op.execute("ALTER TABLE jobs DROP COLUMN embedding")