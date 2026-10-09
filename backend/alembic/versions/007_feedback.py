"""feedback sent from the app

Revision ID: 007_feedback
Revises: 006_razorpay_subscription
Create Date: 2026-10-09 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '007_feedback'
down_revision: Union[str, None] = '006_razorpay_subscription'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    if "feedback" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table(
            "feedback",
            sa.Column("feedback_id", sa.String(64), primary_key=True),
            sa.Column("user_id", sa.String(64), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("page", sa.String(255), nullable=True),
            sa.Column("created_at", sa.String(64), nullable=False),
        )
    op.execute("CREATE INDEX IF NOT EXISTS idx_feedback_created ON feedback(created_at)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_feedback_created")
    op.execute("DROP TABLE IF EXISTS feedback")
