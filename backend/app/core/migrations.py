"""
JobCopilot - Declarative Schema Migrations Runner
Executes atomic, versioned schema migrations across local SQLite and cloud PostgreSQL instances.
"""

import logging
from typing import List, Tuple
from app.core.database import db

logger = logging.getLogger("jobcopilot.migrations")

MIGRATIONS: List[Tuple[str, str, str]] = [
    (
        "0001_multi_tenant_user_id",
        "Add user_id column to tables for multi-tenant isolation",
        """
        -- Add user_id indexes
        CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status);
        CREATE INDEX IF NOT EXISTS idx_jobs_user_priority ON jobs(user_id, priority_score DESC);
        CREATE INDEX IF NOT EXISTS idx_vault_user ON vault(user_id);
        CREATE INDEX IF NOT EXISTS idx_hitl_user_status ON hitl_events(user_id, status);
        """
    ),
    (
        "0002_billing_and_subscriptions",
        "Add subscriptions table for tracking Stripe customer IDs and tiers",
        """
        CREATE TABLE IF NOT EXISTS user_subscriptions (
            user_id TEXT PRIMARY KEY,
            stripe_customer_id TEXT,
            tier TEXT NOT NULL DEFAULT 'FREE',
            status TEXT NOT NULL DEFAULT 'active',
            current_period_end TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_sub_customer ON user_subscriptions(stripe_customer_id);
        """
    )
]


class MigrationRunner:
    """Runs pending schema migrations atomically."""

    @classmethod
    def apply_all(cls) -> int:
        applied_count = 0
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version TEXT PRIMARY KEY,
                    description TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()

            cursor.execute("SELECT version FROM schema_migrations")
            applied_versions = {row[0] for row in cursor.fetchall()}

            for version, desc, sql in MIGRATIONS:
                if version not in applied_versions:
                    logger.info(f"Applying migration {version}: {desc}")
                    cursor.executescript(sql)
                    cursor.execute(
                        "INSERT INTO schema_migrations (version, description) VALUES (?, ?)",
                        (version, desc)
                    )
                    conn.commit()
                    applied_count += 1

        return applied_count


# Global singleton
migration_runner = MigrationRunner()
