"""add expires_at to jobs

Revision ID: 5eef20790b34
Revises: c88014e0b0f2
Create Date: 2026-08-08 16:29:07.309734

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5eef20790b34'
down_revision: Union[str, Sequence[str], None] = 'c88014e0b0f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        'jobs',
        sa.Column(
            'expires_at',
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now() + interval '30 days'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('jobs', 'expires_at')
    