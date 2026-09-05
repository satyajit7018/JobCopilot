# JobCopilot SOC 2 Type II Control Mapping & Audit Matrix

**Effective Date:** September 1, 2026  
**Auditor Reference:** AICPA Trust Services Criteria (TSC) 2017 (Security, Availability, Confidentiality, Privacy)  
**Classification:** Internal Compliance & Customer Audit Document  

This document provides a direct mapping between the AICPA Trust Services Criteria and the automated controls implemented across the JobCopilot codebase, database schema, CI/CD safety gates, and operational policies.

---

## 1. Security & Common Criteria (CC-Series)

| TSC ID | Control Requirement | JobCopilot Implementation | Verification & File Artifacts |
| :--- | :--- | :--- | :--- |
| **CC6.1** | Logical access security controls protect systems against unauthorized access. | Role-Based Access Control (`UserRole`: `CANDIDATE`, `RECRUITER`, `ADMIN`, `SUPERADMIN`), JWT Bearer tokens with 15-minute expiration, and OAuth2 SSO authentication. | `backend/app/api/auth.py`<br>`backend/tests/test_rbac.py` |
| **CC6.2** | Registration, modification, and deletion of logical access credentials are controlled. | Cryptographic password hashing (Argon2 / PBKDF2), automated credential generation for SSO users, secure account recovery workflows. | `backend/app/api/routers/auth_router.py`<br>`backend/tests/test_auth_endpoints.py` |
| **CC6.3** | Access rights are revoked or modified upon termination or role reassignment. | Multi-tenant organization memberships (`Membership`, `OrgRole`: `OWNER`, `ADMIN`, `MEMBER`), immediate session revocation upon password change or account deletion. | `backend/app/api/routers/org_router.py`<br>`backend/app/api/routers/account_router.py` |
| **CC6.6** | Perimeter defense and logical boundaries prevent unauthorized cross-boundary access. | Strict Content Security Policy (CSP) with nonce-based execution (`0 unsafe-inline`), reverse proxy TLS termination, and multi-tenant DB foreign key scoping. | `frontend/sw.js`<br>`backend/app/core/database.py`<br>`backend/tests/test_csp_headers.py` |
| **CC6.7** | Data in transit is protected against interception or unauthorized disclosure. | Mandatory TLS 1.3 encryption across all public REST APIs, WebSocket streaming endpoints (`ws://` upgraded to `wss://`), and database connections. | `backend/app/api/ws_gateway.py`<br>`docs/SECURITY.md` |
| **CC6.8** | Malicious software prevention, input validation, and sanitization. | Pydantic v2 strict request schemas, parameter injection defense, parameterized SQL queries (`?` for SQLite, `%s` for PostgreSQL), zero raw string concatenation. | `backend/app/core/models.py`<br>`backend/tests/test_database_factory.py` |
| **CC7.1** | Vulnerability management and software composition analysis. | Automated Bandit static analysis security testing (SAST) in CI gate (`bandit -ll`), pre-commit dependency audits, and Dependabot vulnerability alerts. | `backend/venv/bin/bandit`<br>`backend/tests/test_bandit_sast.py` |
| **CC7.2** | System monitoring, anomaly detection, and operational health tracking. | Application telemetry, Prometheus-compatible `/metrics` endpoint, rate-limiting middleware (`SlowAPI`), and real-time WebSocket connection state tracking. | `backend/app/api/routers/analytics_router.py`<br>`backend/app/api/ws_gateway.py` |
| **CC7.3** | Incident response evaluation and emergency intervention. | Human-in-the-loop (HITL) emergency halt mechanisms for background autonomous agents, admin impersonation audit trail, automated alert channels. | `backend/app/api/routers/bot_router.py`<br>`backend/app/api/routers/admin_router.py` |
| **CC8.1** | Change management, version control, and database schema migrations. | Alembic reversible migrations verified by automated dual-engine safety gate (`scripts/migration_safety_gate.py`) executing Upgrade -> Downgrade -> Re-upgrade cycles. | `backend/alembic/versions/`<br>`scripts/migration_safety_gate.py` |

---

## 2. Privacy & Trust Criteria (P-Series)

| TSC ID | Control Requirement | JobCopilot Implementation | Verification & File Artifacts |
| :--- | :--- | :--- | :--- |
| **P1.1** | Notice is provided regarding the platform's personal data policies and practices. | Publicly accessible legal endpoints (`GET /api/v1/compliance/legal/tos` and `/legal/dpa`), clear in-app consent collection dialogs. | `backend/app/api/routers/compliance_router.py`<br>`docs/compliance/TERMS_OF_SERVICE.md` |
| **P2.1** | Choices and consents regarding data collection and AI processing are documented and honored. | Granular consent engine recording append-only consent records with client IP, user-agent, and version tracking (`POST /api/v1/compliance/consent`). | `backend/app/core/models.py`<br>`backend/tests/test_compliance_trust_epic_j.py` |
| **P4.1** | Data subjects have access to their personal data for review and export (Portability). | One-click machine-readable JSON data portability export endpoint generating complete encrypted tenant archive (GDPR Article 20). | `backend/app/api/routers/account_router.py`<br>`backend/tests/test_account_router.py` |
| **P4.3** | Personal data is permanently deleted or anonymized upon request (Right to Erasure). | Cryptographic hard deletion purging all candidate records, resume files, stripe subscriptions, and vector indexes (GDPR Article 17). | `backend/app/core/database.py`<br>`backend/app/api/routers/account_router.py` |
| **P6.1** | Data retention and disposal policies are enforced. | Deterministic audit log retention schedules (365-day compliance log cycle, 30-day snapshot backup lifecycle, automated log pruning). | `docs/compliance/AUDIT_LOG_RETENTION_POLICY.md`<br>`backend/app/api/routers/backup_router.py` |

---

## 3. Availability Criteria (A-Series)

| TSC ID | Control Requirement | JobCopilot Implementation | Verification & File Artifacts |
| :--- | :--- | :--- | :--- |
| **A1.1** | System capacity and operational resilience are maintained. | SQLite WAL concurrency mode with connection pooler and PostgreSQL enterprise adapter with fallback health probes. | `backend/app/core/database.py`<br>`backend/app/core/postgres_adapter.py` |
| **A1.2** | Data backup, replication, and disaster recovery processes are tested and documented. | Automated backup engine (`backup_router.py`), point-in-time recovery, zero-data-loss RPO (<15 mins) and rapid RTO (<30 mins) disaster recovery plan. | `backend/app/api/routers/backup_router.py`<br>`docs/DISASTER_RECOVERY.md` |
| **A1.3** | Continuity of service during infrastructure degradation. | Graceful degradation for third-party LLM timeouts, offline PWA caching service worker (`sw.js`), and queued background retry workers. | `frontend/sw.js`<br>`backend/app/core/bot.py` |

---

## 4. Continuous Audit & Compliance Automation

JobCopilot maintains audit-readiness through automated CI pipeline gates:
1. **Migration Gate:** `scripts/migration_safety_gate.py` ensures 100% reversible database schema changes.
2. **Security Gate:** `bandit -r backend/app scripts -ll` ensures 0 High and 0 Medium security vulnerabilities.
3. **Coverage Gate:** `pytest --cov=backend/app --cov-fail-under=80` ensures enterprise-grade automated regression testing.
4. **Stress & Concurrency Gate:** `stress_test_30_deep_loops.py` ensures zero resource leaks or deadlocks across 30 sustained simulation cycles.
