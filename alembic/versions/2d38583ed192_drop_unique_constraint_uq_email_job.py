"""drop unique constraint uq_email_job

Revision ID: 2d38583ed192
Revises: 
Create Date: 2026-09-04 11:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2d38583ed192'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('uq_email_job', 'email_records', type_='unique')


def downgrade() -> None:
    op.create_unique_constraint('uq_email_job', 'email_records', ['email', 'job_id'])
