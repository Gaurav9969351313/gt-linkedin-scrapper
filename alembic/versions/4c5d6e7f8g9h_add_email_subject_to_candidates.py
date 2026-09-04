"""add email_subject to candidates

Revision ID: 4c5d6e7f8g9h
Revises: 3a4b5c6d7e8f
Create Date: 2026-09-04 17:06:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '4c5d6e7f8g9h'
down_revision: Union[str, None] = '3a4b5c6d7e8f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('email_subject', sa.String(length=512), nullable=True))
    op.create_index('ix_candidates_email_subject', 'candidates', ['email_subject'], unique=False)
    op.execute("UPDATE candidates SET email_subject = 'No Subject' WHERE email_subject IS NULL")
    op.alter_column('candidates', 'email_subject', nullable=False)


def downgrade() -> None:
    op.drop_index('ix_candidates_email_subject', table_name='candidates')
    op.drop_column('candidates', 'email_subject')
