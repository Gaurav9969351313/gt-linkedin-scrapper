"""add candidates table

Revision ID: 3a4b5c6d7e8f
Revises: 2d38583ed192
Create Date: 2026-09-04 15:46:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3a4b5c6d7e8f'
down_revision: Union[str, None] = '2d38583ed192'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'candidates',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=256), nullable=False),
        sa.Column('number', sa.String(length=64), nullable=False),
        sa.Column('subscription', sa.String(length=128), nullable=False),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('email', sa.String(length=256), nullable=False),
        sa.Column('email_password', sa.String(length=256), nullable=False),
        sa.Column('resume', sa.String(length=512), nullable=True),
        sa.Column('email_body', sa.Text(), nullable=False),
        sa.Column('tag', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_candidates_email', 'candidates', ['email'], unique=False)
    op.create_index('ix_candidates_tag', 'candidates', ['tag'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_candidates_tag', table_name='candidates')
    op.drop_index('ix_candidates_email', table_name='candidates')
    op.drop_table('candidates')
