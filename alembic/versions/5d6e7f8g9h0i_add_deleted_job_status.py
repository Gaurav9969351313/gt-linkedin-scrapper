"""add deleted job status for soft delete

Revision ID: 5d6e7f8g9h0i
Revises: 4c5d6e7f8g9h
Create Date: 2026-10-20 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '5d6e7f8g9h0i'
down_revision: Union[str, None] = '4c5d6e7f8g9h'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('ck_job_status', 'jobs', type_='check')
    op.create_check_constraint(
        'ck_job_status', 'jobs',
        "status IN ('idle','running','completed','error','hold','deleted')",
    )


def downgrade() -> None:
    op.execute("UPDATE jobs SET status = 'hold' WHERE status = 'deleted'")
    op.drop_constraint('ck_job_status', 'jobs', type_='check')
    op.create_check_constraint(
        'ck_job_status', 'jobs',
        "status IN ('idle','running','completed','error','hold')",
    )
