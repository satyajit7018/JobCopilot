# JobCopilot Audit Log Retention & Archival Policy

**Effective Date:** September 1, 2026  
**Version:** 1.0  
**Compliance Standards:** SOC 2 CC7.2; GDPR Article 30; PCI-DSS Requirement 10; ISO/IEC 27001:2022 A.12.4  
**Classification:** Internal Operational Policy & Audit Mandate  

---

## 1. Purpose & Scope

This policy establishes strict standards for capturing, protecting, indexing, retaining, and securely disposing of system event logs, security audit records, administrative actions, and candidate consent histories across JobCopilot platforms.

Adherence to this policy ensures forensic readiness, tamper resistance, and compliance with global data protection laws and external audit standards.

---

## 2. Categorization of Logs & Mandatory Retention Schedules

JobCopilot categorizes logs into four distinct tiers based on legal necessity, forensic value, and regulatory mandates:

| Log Tier | Category Description | Target Tables / Storage | Minimum Retention | Archival Format |
| :--- | :--- | :--- | :--- | :--- |
| **Tier 1: Consent & Legal Proof** | Candidate consent grants, revocations, policy versions, client IP, user agent | `user_consents` table | **7 Years** (Statutory limitation period) | Immutable append-only database records & compressed encrypted archives |
| **Tier 2: Admin & Privilege Audits** | Admin impersonation, tenant role changes, organization mutations, account erasures | `admin_audit_logs` table | **3 Years** | Structured database records with cryptographic hash chaining |
| **Tier 3: Authentication & Security** | User logins, failed authentication attempts, SSO handshakes, rate-limit triggers | Application auth logs & WAF edge logs | **1 Year** | Centralized SIEM / Log aggregator with search indexing |
| **Tier 4: Telemetry & Performance** | API request latencies, bot automation steps, outbound HTTP response codes | Telemetry buffers & Prometheus time-series | **90 Days** | High-throughput time-series store with automated rolling purge |
| **Tier 5: Database Backups** | Transactional snapshots and SQLite WAL / PostgreSQL dump archives | Encrypted cloud bucket (`jobcopilot-backups`) | **30 Days** | AES-256 encrypted TAR/GZ archives with rolling lifecycle rotation |

---

## 3. Immutability & Tamper Resistance Controls

1. **Append-Only Operations:**
   - The `user_consents` and `admin_audit_logs` tables permit only `INSERT` and `SELECT` operations.
   - Application adapters do not expose `UPDATE` or `DELETE` methods for these audit tables.
2. **Database Constraint Protections:**
   - In PostgreSQL production instances, Row-Level Security (RLS) policies prohibit `UPDATE` queries on audit log tables even for administrative database roles.
3. **Cryptographic Integrity:**
   - Sensitive audit markers include deterministic timestamps (`datetime.now().isoformat()`) and client network provenance to guarantee non-repudiation.

---

## 4. Log Storage Architecture & Encryption

1. **Encryption Standards:**
   - **In Transit:** All log ingestion and export traffic is secured using TLS 1.3.
   - **At Rest:** Primary database tables and cloud archival storage buckets enforce AES-256 encryption.
2. **Access Restrictions:**
   - Audit logs are accessible strictly via authenticated, role-gated APIs (`require_admin` dependency for admin logs, candidate ownership filtering for consent logs).
   - Direct database access to production log storage is restricted to authorized Security Personnel.

---

## 5. Automated Pruning & Disposal Protocols

1. **Scheduled Automated Purging:**
   - Telemetry and performance metrics exceeding ninety (90) days are purged automatically via database TTL indexes or scheduled background cron jobs.
   - Database backup snapshots older than thirty (30) days are automatically expired by cloud object lifecycle policies.
2. **Candidate Account Erasure Interaction:**
   - When a candidate invokes `DELETE /api/v1/account` (GDPR Article 17), personal candidate records, resumes, and profile answers are permanently wiped immediately.
   - To satisfy legal accountability requirements under GDPR Article 7(1) ("demonstrate that the data subject has consented"), consent timestamp markers and erasure acknowledgment records are pseudonymized and retained in cold audit archives.

---

## 6. Audit Trail Export & Incident Response Forensics

1. **Forensic Export:**
   - Security personnel can extract filtered, machine-readable JSON/CSV audit trails within four (4) hours of an active incident investigation.
2. **Auditor Verification:**
   - During external SOC 2 or ISO 27001 assessments, audit log samples and retention timestamps are provided via programmatic export scripts with accompanying SHA-256 checksums to verify evidentiary chain of custody.
