"""
JobCopilot - Database Factory & Adapter Architecture Test Suite
Validates that get_db() correctly yields a DatabaseAdapter and PostgreSQL fallback.
"""

from app.core.database import get_db, db, DatabaseManager
from app.core.db_adapter import DatabaseAdapter
from app.core.postgres_adapter import PostgresDatabaseAdapter


def test_database_factory_default():
    """Asserts get_db() returns DatabaseAdapter instance."""
    adapter = get_db()
    assert isinstance(adapter, DatabaseAdapter)
    assert isinstance(adapter, DatabaseManager)


def test_postgres_adapter_instantiation():
    """Asserts PostgresDatabaseAdapter instantiates cleanly without crashing."""
    pg = PostgresDatabaseAdapter("postgresql://user:pass@localhost:5432/jobcopilot_test")
    assert isinstance(pg, DatabaseAdapter)
