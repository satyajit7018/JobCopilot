"""unique constraint on apply_ledger(user_id, job_id) to prevent duplicate applications
Revision ID: 004_apply_ledger_unique
Revises: 003_compliance
Create Date: 2026-09-15 23:20:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '004_apply_ledger_unique'
down_revision: Union[str, None] = '003_compliance'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Ensure apply_ledger table exists (fresh migration from base)
    op.execute("""
        CREATE TABLE IF NOT EXISTS apply_ledger (
            ledger_id VARCHAR(64) PRIMARY KEY,
            user_id VARCHAR(64) NOT NULL DEFAULT 'default',
            job_id VARCHAR(64) NOT NULL,
            job_fingerprint VARCHAR(255) NOT NULL,
            status VARCHAR(64) NOT NULL,
            attempt_count INTEGER DEFAULT 1,
            max_retries INTEGER DEFAULT 3,
            last_error_category VARCHAR(64),
            last_error_message TEXT,
            confirmation_id VARCHAR(128),
            screenshot_path TEXT,
            idempotency_key VARCHAR(128),
            created_at VARCHAR(64) NOT NULL,
            updated_at VARCHAR(64) NOT NULL
        )
    """)
    # 1. Deduplicate existing rows (keep newest per (user_id, job_id) pair)
    op.execute("""
        DELETE FROM apply_ledger WHERE ledger_id IN (
            SELECT ledger_id FROM (
                SELECT ledger_id, ROW_NUMBER() OVER (PARTITION BY user_id, job_id ORDER BY updated_at DESC) AS rn
                FROM apply_ledger
            ) t WHERE t.rn > 1
        )
    """)
    # 2. Create unique index
    op.create_index("uq_apply_ledger_user_job", "apply_ledger", ["user_id", "job_id"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_apply_ledger_user_job", "apply_ledger")
    op.execute("DROP TABLE IF EXISTS apply_ledger")
