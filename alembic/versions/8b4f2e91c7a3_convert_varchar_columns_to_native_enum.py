"""convert varchar columns to native postgres enum types

Revision ID: 8b4f2e91c7a3
Revises: f3a8c1d92b4e
Create Date: 2026-09-01 00:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8b4f2e91c7a3'
down_revision: Union[str, Sequence[str], None] = 'f3a8c1d92b4e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # --- 1. Create the native Postgres enum types ---
    userrole = sa.Enum('employer', 'candidate', name='userrole')
    jobtype = sa.Enum('full_time', 'part_time', 'contract', name='jobtype')
    jobstatus = sa.Enum('open', 'closed', name='jobstatus')
    applicationstatus = sa.Enum(
        'pending', 'reviewed', 'rejected', 'accepted', name='applicationstatus'
    )

    userrole.create(op.get_bind(), checkfirst=True)
    jobtype.create(op.get_bind(), checkfirst=True)
    jobstatus.create(op.get_bind(), checkfirst=True)
    applicationstatus.create(op.get_bind(), checkfirst=True)

    # --- 2. users.role: varchar -> userrole ---
    op.alter_column(
        'users', 'role',
        existing_type=sa.String(),
        type_=userrole,
        postgresql_using='role::userrole',
        nullable=False,
    )

    # --- 3. jobs.job_type: varchar -> jobtype ---
    op.alter_column(
        'jobs', 'job_type',
        existing_type=sa.String(),
        type_=jobtype,
        postgresql_using='job_type::jobtype',
        nullable=False,
    )

    # --- 4. jobs.status: varchar -> jobstatus (has a default, drop/re-add) ---
    op.alter_column('jobs', 'status', server_default=None)
    op.alter_column(
        'jobs', 'status',
        existing_type=sa.String(),
        type_=jobstatus,
        postgresql_using='status::jobstatus',
        nullable=False,
    )
    op.alter_column(
        'jobs', 'status',
        server_default=sa.text("'open'::jobstatus"),
    )

    # --- 5. applications.status: varchar -> applicationstatus (has a default) ---
    op.alter_column('applications', 'status', server_default=None)
    op.alter_column(
        'applications', 'status',
        existing_type=sa.String(),
        type_=applicationstatus,
        postgresql_using='status::applicationstatus',
        nullable=False,
    )
    op.alter_column(
        'applications', 'status',
        server_default=sa.text("'pending'::applicationstatus"),
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Reverse order: columns back to varchar, then drop types

    op.alter_column('applications', 'status', server_default=None)
    op.alter_column(
        'applications', 'status',
        existing_type=sa.Enum(name='applicationstatus'),
        type_=sa.String(),
        postgresql_using='status::text',
        nullable=False,
    )
    op.alter_column('applications', 'status', server_default='pending')

    op.alter_column('jobs', 'status', server_default=None)
    op.alter_column(
        'jobs', 'status',
        existing_type=sa.Enum(name='jobstatus'),
        type_=sa.String(),
        postgresql_using='status::text',
        nullable=False,
    )
    op.alter_column('jobs', 'status', server_default='open')

    op.alter_column(
        'jobs', 'job_type',
        existing_type=sa.Enum(name='jobtype'),
        type_=sa.String(),
        postgresql_using='job_type::text',
        nullable=False,
    )

    op.alter_column(
        'users', 'role',
        existing_type=sa.Enum(name='userrole'),
        type_=sa.String(),
        postgresql_using='role::text',
        nullable=False,
    )

    sa.Enum(name='applicationstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='jobstatus').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='jobtype').drop(op.get_bind(), checkfirst=True)
    sa.Enum(name='userrole').drop(op.get_bind(), checkfirst=True)