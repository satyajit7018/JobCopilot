"""store each user's Razorpay subscription (Premium plan)

Revision ID: 006_razorpay_subscription
Revises: 005_stripe_customer_id
Create Date: 2026-10-09 00:00:00.000000

Dialect-aware like 005: SQLite has no ADD COLUMN IF NOT EXISTS, so existence is
checked with the inspector.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '006_razorpay_subscription'
down_revision: Union[str, None] = '005_stripe_customer_id'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = "idx_users_razorpay_sub"
COLUMNS = (
    ("razorpay_subscription_id", sa.String(64)),
    ("subscription_status", sa.String(32)),
    ("subscription_current_end", sa.String(64)),
)


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    for name, type_ in COLUMNS:
        if not _has_column("users", name):
            op.add_column("users", sa.Column(name, type_, nullable=True))
    op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} ON users(razorpay_subscription_id) "
               "WHERE razorpay_subscription_id IS NOT NULL")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
    present = [name for name, _ in COLUMNS if _has_column("users", name)]
    if present:
        with op.batch_alter_table("users") as batch:
            for name in present:
                batch.drop_column(name)
