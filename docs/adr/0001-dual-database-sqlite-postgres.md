# 1. Dual Database Architecture (SQLite WAL and PostgreSQL)

Date: 2026-09-06

## Status

Accepted

## Context

JobCopilot was originally engineered as an autonomous desktop agent running locally on a user's machine with single-user SQLite storage. As the product expanded into multi-tenant cloud SaaS deployment, requirements emerged for:
1. High-concurrency ACID transactions, connection pooling, and remote persistence (PostgreSQL with async/sync drivers).
2. Zero-config, frictionless local developer workflows and offline desktop operation without spinning up containerized database infrastructure (SQLite in Write-Ahead-Logging mode).
3. Uniform business logic across both desktop local mode and multi-tenant cloud mode.

## Decision

We adopted an explicit **Dual Database Adapter Pattern**:
- Defined an abstract base interface `DatabaseAdapter` in `backend/app/core/db_adapter.py`.
- Implemented `DatabaseManager` in `backend/app/core/database.py` providing complete SQLite WAL operation (`PRAGMA journal_mode=WAL`, `busy_timeout=15000`, `synchronous=NORMAL`).
- Implemented `PostgresDatabaseAdapter` in `backend/app/core/postgres_adapter.py` providing production connection pooling via `psycopg2.pool.ThreadedConnectionPool`.
- Dynamic factory routing in `get_db()`:
  - If `DATABASE_URL` is set and begins with `postgres://` or `postgresql://`, instantiate `PostgresDatabaseAdapter`.
  - Otherwise, default fail-safe to SQLite WAL (`DatabaseManager`).
- **Static Parameterized SQL Invariant**: Zero f-strings or dynamic SQL string concatenation are permitted in query construction. SQLite uses `?` parameterization; Postgres uses `%s` parameterization.
- **Alembic Dual Compatibility**: Migrations in `backend/alembic/versions/` must validate cleanly against both SQLite and PostgreSQL via the `scripts/migration_safety_gate.py`.

## Consequences

### Positive
- Developers can clone the repository and run the test suite or server immediately without installing PostgreSQL.
- Production deployments can switch to managed RDS PostgreSQL simply by setting the `DATABASE_URL` environment variable.
- Strict multi-tenant row-level tenant filtering (`user_id = ?` / `user_id = %s`) is maintained identically across both adapters.

### Negative / Trade-offs
- New database tables and query methods must be implemented in both adapters (`database.py` and `postgres_adapter.py`), maintaining signature parity.
- Complex Postgres-specific features (e.g., custom trigger procedures or non-standard SQL extensions) must provide clean functional fallbacks in SQLite.
