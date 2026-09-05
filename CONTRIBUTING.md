# Contributing to JobCopilot

Thank you for contributing to **JobCopilot**, the universal autonomous career operating system.

Please read through these guidelines to ensure code quality, security posture, and test coverage standards are maintained across all contributions.

---

## 1. Quickstart & Local Environment

### Prerequisites
- Python 3.9+ (or higher)
- Node.js 18+ (for frontend tools)
- SQLite 3 with WAL support (default local storage)

### Setup
```bash
# Clone the repository
git clone https://github.com/satyajit7018/JobCopilot.git
cd JobCopilot

# Create and activate virtual environment
python3 -m venv backend/venv
source backend/venv/bin/activate

# Install dependencies and dev tools
pip install -r backend/requirements.txt
pip install ruff black mypy pre-commit
```

---

## 2. Code Quality & Pre-Commit Hooks

We enforce rigorous code hygiene using **Ruff**, **Black**, **Mypy**, and **Bandit**.

### Setting Up Git Hooks
```bash
pre-commit install
```

### Manual Quality Checks
```bash
# Linting with Ruff
ruff check backend/app scripts

# Formatting with Black
black --check backend/app scripts

# Type checking with Mypy
mypy backend/app/core/settings.py backend/app/core/models.py backend/app/analytics/

# Security SAST Audit with Bandit
bandit -r backend/app scripts -ll
```

---

## 3. Architecture Invariants & Standards

Every PR must uphold the following core architectural rules:

1. **Static Parameterized SQL (Zero SQL Injection)**:
   - **Never** use f-strings or string interpolation to construct SQL queries.
   - Use `?` parameterization for SQLite (`DatabaseManager`) and `%s` parameterization for PostgreSQL (`PostgresDatabaseAdapter`).
   - Every database modification must be supported in both database adapters.

2. **Strict Multi-Tenant Isolation**:
   - Every data query or mutation on tenant assets (`jobs`, `profiles`, `vault`, `analytics_events`, etc.) must include an explicit `user_id` constraint resolved from the authenticated session (`get_current_user`).
   - Unauthenticated routes must never access tenant storage.

3. **Ethical Browser Automation**:
   - **Never** attempt to bypass or defeat CAPTCHAs programmatically.
   - Always escalate CAPTCHAs and unknown high-entropy form fields to Human-in-the-Loop (`HITLEvent`).

4. **API Versioning**:
   - New endpoints must be registered under `/api/v1/` in their respective domain router under `backend/app/api/routers/`.

---

## 4. Testing & CI Coverage Gate

All contributions must pass the full test suite with **≥ 80% test coverage**:

```bash
# Run test suite with CI coverage gate
PYTHONPATH=backend:. pytest backend/tests/ -q --cov=backend/app --cov-fail-under=80

# Run 30-Loop Subsystem Deep Stress Audit
PYTHONPATH=backend:. python backend/stress_test_30_deep_loops.py
```

---

## 5. Commit & Pull Request Guidelines

- Keep pull requests focused on a single responsibility or epic.
- Reference relevant Architecture Decision Records in `docs/adr/` for significant design decisions.
- Verify that `scripts/migration_safety_gate.py` passes whenever modifying or adding Alembic migrations.
