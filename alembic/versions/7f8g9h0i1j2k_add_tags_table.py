"""add tags table; fix jobs id sequence

Revision ID: 7f8g9h0i1j2k
Revises: 6e7f8g9h0i1j
Create Date: 2026-10-23 19:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '7f8g9h0i1j2k'
down_revision: Union[str, None] = '6e7f8g9h0i1j'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Copied (not imported) so this migration never changes if the model's defaults do.
DEFAULT_TAGS = [
    ("devops", "DevOps"),
    ("java", "Java"),
    ("qa", "QA"),
    ("freshers", "Freshers"),
    ("data_engineer", "Data Engineer"),
]


def upgrade() -> None:
    tags = op.create_table(
        'tags',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=128), nullable=False),
        sa.Column('description', sa.String(length=512), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tags_name', 'tags', ['name'], unique=True)
    op.bulk_insert(tags, [{"name": n, "label": l} for n, l in DEFAULT_TAGS])

    # Any other tag already used by data becomes a managed tag too.
    op.execute(
        """
        INSERT INTO tags (name, label)
        SELECT DISTINCT t.tag, t.tag FROM (
            SELECT tag FROM jobs UNION SELECT tag FROM candidates UNION SELECT tag FROM email_records
        ) t
        WHERE t.tag IS NOT NULL AND t.tag <> '' AND t.tag NOT IN (SELECT name FROM tags)
        """
    )

    # Jobs were seeded with explicit ids, leaving the id sequence behind; new jobs would collide.
    op.execute("SELECT setval(pg_get_serial_sequence('jobs', 'id'), COALESCE((SELECT MAX(id) FROM jobs), 0) + 1, false)")


def downgrade() -> None:
    op.drop_index('ix_tags_name', table_name='tags')
    op.drop_table('tags')
