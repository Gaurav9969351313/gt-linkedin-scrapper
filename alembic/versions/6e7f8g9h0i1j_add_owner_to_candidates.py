"""add owner_id to candidates

Revision ID: 6e7f8g9h0i1j
Revises: 5d6e7f8g9h0i
Create Date: 2026-10-23 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6e7f8g9h0i1j'
down_revision: Union[str, None] = '5d6e7f8g9h0i'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('candidates', sa.Column('owner_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_candidates_owner_id_app_users', 'candidates', 'app_users', ['owner_id'], ['id'], ondelete='SET NULL'
    )
    op.create_index('ix_candidates_owner_id', 'candidates', ['owner_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_candidates_owner_id', table_name='candidates')
    op.drop_constraint('fk_candidates_owner_id_app_users', 'candidates', type_='foreignkey')
    op.drop_column('candidates', 'owner_id')
