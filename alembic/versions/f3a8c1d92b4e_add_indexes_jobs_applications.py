"""add indexes on jobs.employer_id, applications.candidate_id, jobs status+created_at

Revision ID: f3a8c1d92b4e
Revises: 5eef20790b34
Create Date: 2026-09-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3a8c1d92b4e'
down_revision: Union[str, Sequence[str], None] = '5eef20790b34'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_index(
        op.f('ix_jobs_employer_id'), 'jobs', ['employer_id'], unique=False
    )
    op.create_index(
        op.f('ix_applications_candidate_id'), 'applications', ['candidate_id'], unique=False
    )
    op.create_index(
        'ix_jobs_status_created_at', 'jobs', ['status', 'created_at'], unique=False
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_jobs_status_created_at', table_name='jobs')
    op.drop_index(op.f('ix_applications_candidate_id'), table_name='applications')
    op.drop_index(op.f('ix_jobs_employer_id'), table_name='jobs')