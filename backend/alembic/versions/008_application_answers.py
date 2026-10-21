"""saved application answers: reuse scope, job, last confirmed, confirmed wordings

Revision ID: 008_application_answers
Revises: 007_feedback
Create Date: 2026-10-21 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '008_application_answers'
down_revision: Union[str, None] = '007_feedback'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

COLUMNS = (
    sa.Column("scope", sa.String(16), nullable=False, server_default="any"),
    sa.Column("job_id", sa.String(64), nullable=True),
    sa.Column("confirmed_at", sa.String(64), nullable=True),
    sa.Column("aliases", sa.JSON(), nullable=False, server_default="[]"),
)


def upgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("vault")}
    for column in COLUMNS:
        if column.name not in existing:
            op.add_column("vault", column)


def downgrade() -> None:
    existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("vault")}
    for column in reversed(COLUMNS):
        if column.name in existing:
            op.drop_column("vault", column.name)
