#!/usr/bin/env python3
"""
JobCopilot - CI/CD Migration Safety Gate
Validates Alembic database migrations in an isolated ephemeral database before deployment.
Verifies:
1. Dry-run upgrade to head
2. Complete downgrade to base (rollback validation)
3. Re-upgrade to head (idempotency validation)
Fails CI/CD pipeline if any migration script fails or leaves orphaned locks/tables.
"""

import os
import sys
import tempfile
import logging
from pathlib import Path
from alembic.config import Config
from alembic import command
from sqlalchemy import create_engine, inspect

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("migration_safety_gate")


def run_migration_safety_gate() -> bool:
    repo_root = Path(__file__).resolve().parent.parent
    backend_dir = repo_root / "backend"
    alembic_ini_path = backend_dir / "alembic.ini"

    if not alembic_ini_path.exists():
        logger.error(f"alembic.ini not found at {alembic_ini_path}")
        return False

    with tempfile.TemporaryDirectory() as tmp_dir:
        test_db_path = Path(tmp_dir) / "migration_gate_test.db"
        test_db_url = f"sqlite:///{test_db_path}"

        logger.info(f"Initializing ephemeral gate database at {test_db_url}")
        os.environ["DATABASE_URL"] = test_db_url
        os.environ["DATA_DIR"] = tmp_dir

        alembic_cfg = Config(str(alembic_ini_path))
        alembic_cfg.set_main_option("script_location", str(backend_dir / "alembic"))
        alembic_cfg.set_main_option("sqlalchemy.url", test_db_url)

        try:
            # Phase 1: Forward Migration to Head
            logger.info(">>> Phase 1: Testing upgrade to head...")
            command.upgrade(alembic_cfg, "head")
            logger.info("✓ Upgrade to head succeeded.")

            # Validate tables created
            engine = create_engine(test_db_url)
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            logger.info(f"✓ Created tables: {', '.join(tables)}")
            if not tables:
                logger.error("Migration safety failure: No tables were created by upgrade head.")
                return False

            # Phase 2: Rollback to Base
            logger.info(">>> Phase 2: Testing downgrade to base (Rollback safety)...")
            command.downgrade(alembic_cfg, "base")
            logger.info("✓ Downgrade to base succeeded.")

            # Validate rollback cleaned up
            inspector = inspect(engine)
            remaining_tables = [t for t in inspector.get_table_names() if t != "alembic_version"]
            if remaining_tables:
                logger.error(f"Migration rollback safety breach: Tables remained after downgrade base: {remaining_tables}")
                return False
            logger.info("✓ Schema cleanly rolled back.")

            # Phase 3: Idempotency Re-upgrade
            logger.info(">>> Phase 3: Testing re-upgrade to head (Idempotency validation)...")
            command.upgrade(alembic_cfg, "head")
            logger.info("✓ Re-upgrade to head succeeded.")

            logger.info("==================================================")
            logger.info("MIGRATION SAFETY GATE: PASSED (All 3 phases clean)")
            logger.info("==================================================")
            return True

        except Exception as exc:
            logger.error(f"Migration safety gate FAILED with error: {exc}", exc_info=True)
            return False


if __name__ == "__main__":
    success = run_migration_safety_gate()
    sys.exit(0 if success else 1)
