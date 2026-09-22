"""link users to their Stripe customer id (audit P1-6 / P1-7)

Revision ID: 005_stripe_customer_id
Revises: 004_apply_ledger_unique
Create Date: 2026-09-22 00:00:00.000000

Dialect-aware: runs on both PostgreSQL (CI, production) and SQLite (the local
migration safety gate). SQLite has no ADD COLUMN IF NOT EXISTS, so existence is
checked with the inspector instead.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = '005_stripe_customer_id'
down_revision: Union[str, None] = '004_apply_ledger_unique'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

INDEX = "idx_users_stripe_customer"


def _has_column(table: str, column: str) -> bool:
    return column in {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if not _has_column("users", "stripe_customer_id"):
        op.add_column("users", sa.Column("stripe_customer_id", sa.String(64), nullable=True))
    # Partial unique index: supported by both PostgreSQL and SQLite (3.8+).
    op.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {INDEX} ON users(stripe_customer_id) "
               "WHERE stripe_customer_id IS NOT NULL")


def downgrade() -> None:
    op.execute(f"DROP INDEX IF EXISTS {INDEX}")
    if _has_column("users", "stripe_customer_id"):
        with op.batch_alter_table("users") as batch:
            batch.drop_column("stripe_customer_id")
