"""
Parity guard for the database layer (plan.md P0-0).

Ensures both concrete adapters fully implement the DatabaseAdapter ABC, so a
method that exists on one backend can never silently be missing on the other
(the historical split-brain bug where Postgres lacked auth/token/usage methods).

Uses ABCMeta's __abstractmethods__ — the frozenset of abstract methods a class
did NOT override. Empty means the class is fully concrete and instantiable; a
non-empty set is exactly the parity gap. No live DB connection required.
"""

from app.core.database import DatabaseManager
from app.core.db_adapter import DatabaseAdapter
from app.core.postgres_adapter import PostgresDatabaseAdapter


def test_both_adapters_subclass_the_abc():
    assert issubclass(DatabaseManager, DatabaseAdapter)
    assert issubclass(PostgresDatabaseAdapter, DatabaseAdapter)


def test_sqlite_adapter_implements_every_abstract_method():
    missing = DatabaseManager.__abstractmethods__
    assert missing == frozenset(), f"DatabaseManager is missing abstract methods: {sorted(missing)}"


def test_postgres_adapter_implements_every_abstract_method():
    missing = PostgresDatabaseAdapter.__abstractmethods__
    assert missing == frozenset(), f"PostgresDatabaseAdapter is missing abstract methods: {sorted(missing)}"


def test_abc_actually_declares_abstract_methods():
    # Guards against the ABC being emptied (which would make the two tests above vacuously pass).
    abstract_names = {
        name for name in dir(DatabaseAdapter)
        if getattr(getattr(DatabaseAdapter, name, None), "__isabstractmethod__", False)
    }
    assert len(abstract_names) >= 20, (
        f"Expected the DatabaseAdapter ABC to declare a substantial abstract surface, "
        f"found only {len(abstract_names)}: {sorted(abstract_names)}"
    )
