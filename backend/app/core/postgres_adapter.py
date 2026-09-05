"""
JobCopilot - PostgreSQL Production Database Adapter
Provides enterprise-grade, high-concurrency PostgreSQL connection pooling and
multi-tenant query execution with fail-safe schema bootstrapping and PII encryption.
"""

import json
import logging
from typing import List, Dict, Optional, Any
from datetime import datetime

from app.core.models import (
    User, CandidateProfile, VaultEntry, JobListing,
    HITLEvent, ApplicationStatus, OutreachRecord, EmailMessage, JobCheckpoint,
    ApplyLedgerEntry, ApplyLedgerStatus,
    Organization, Membership, AdminAuditLog, OrgRole,
    AnalyticsEvent, ABExperiment, ABVariant, ABAssignment, ConversionSignal,
    UserConsent, ConsentType
)
from app.core.db_adapter import DatabaseAdapter
from app.core.credential_vault import cred_vault

logger = logging.getLogger("jobcopilot.postgres")


class PostgresDatabaseAdapter(DatabaseAdapter):
    """Production PostgreSQL Adapter with Threaded Connection Pooling and Multi-Tenant Isolation."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self._pool = None
        self._init_pool()

    def _init_pool(self):
        try:
            import psycopg2
            from psycopg2.pool import ThreadedConnectionPool
            self._pool = ThreadedConnectionPool(minconn=2, maxconn=20, dsn=self.database_url)
            self._init_tables()
            logger.info("PostgreSQL connection pool initialized successfully.")
        except Exception as e:
            logger.warning(f"PostgreSQL pool initialization deferred or unavailable: {e}")

    def get_connection(self):
        if not self._pool:
            raise RuntimeError("PostgreSQL connection pool is not initialized.")
        return self._pool.getconn()

    def release_connection(self, conn):
        if self._pool and conn:
            self._pool.putconn(conn)

    def _init_tables(self):
        """Bootstraps PostgreSQL tables if not already managed by Alembic."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id VARCHAR(64) PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name VARCHAR(255) DEFAULT '',
                    role VARCHAR(32) DEFAULT 'FREE',
                    is_active BOOLEAN DEFAULT TRUE,
                    email_verified BOOLEAN DEFAULT FALSE,
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_users_email ON users(email);

                CREATE TABLE IF NOT EXISTS profiles (
                    id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    data JSONB NOT NULL,
                    updated_at VARCHAR(64) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS vault (
                    qa_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    slot_type VARCHAR(64) NOT NULL,
                    slot_key VARCHAR(128) NOT NULL,
                    question_pattern TEXT NOT NULL,
                    embedding JSONB NOT NULL,
                    answer_template TEXT NOT NULL,
                    dynamic_variables JSONB NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    last_used_at VARCHAR(64),
                    created_at VARCHAR(64) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS jobs (
                    job_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    fingerprint VARCHAR(128) NOT NULL,
                    platform VARCHAR(64) NOT NULL,
                    company VARCHAR(255) NOT NULL,
                    title VARCHAR(255) NOT NULL,
                    location VARCHAR(255) DEFAULT 'Remote / India',
                    url TEXT NOT NULL,
                    description TEXT DEFAULT '',
                    salary_range VARCHAR(128),
                    seniority_level VARCHAR(64),
                    posted_date VARCHAR(64),
                    match_score DOUBLE PRECISION DEFAULT 0.0,
                    priority_score DOUBLE PRECISION DEFAULT 0.0,
                    match_reasons JSONB DEFAULT '[]',
                    missing_skills JSONB DEFAULT '[]',
                    status VARCHAR(64) NOT NULL,
                    submission_mode VARCHAR(32),
                    applied_at VARCHAR(64),
                    application_id VARCHAR(128),
                    confirmation_screenshot_path TEXT,
                    notes TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_pg_jobs_user_status ON jobs(user_id, status);

                CREATE TABLE IF NOT EXISTS hitl_events (
                    event_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    job_id VARCHAR(64) NOT NULL,
                    company VARCHAR(255) NOT NULL,
                    role_title VARCHAR(255) NOT NULL,
                    question_text TEXT NOT NULL,
                    input_type VARCHAR(64) NOT NULL,
                    options JSONB,
                    ai_suggested_draft TEXT,
                    user_answer TEXT,
                    status VARCHAR(64) NOT NULL,
                    screenshot_path TEXT,
                    dom_snapshot TEXT,
                    field_selector VARCHAR(255),
                    created_at VARCHAR(64) NOT NULL,
                    resolved_at VARCHAR(64)
                );

                CREATE TABLE IF NOT EXISTS outreach_records (
                    outreach_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    job_id VARCHAR(64) NOT NULL,
                    channel VARCHAR(64) NOT NULL,
                    recipient_name VARCHAR(255),
                    recipient_title VARCHAR(255),
                    recipient_contact VARCHAR(255),
                    message_content TEXT NOT NULL,
                    status VARCHAR(64) NOT NULL,
                    sent_at VARCHAR(64),
                    created_at VARCHAR(64) NOT NULL
                );

                CREATE TABLE IF NOT EXISTS emails (
                    message_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    sender VARCHAR(255) NOT NULL,
                    recipient VARCHAR(255) NOT NULL,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    received_at VARCHAR(64) NOT NULL,
                    associated_job_id VARCHAR(64),
                    intent VARCHAR(64) NOT NULL,
                    scheduling_links JSONB,
                    has_tracking_pixels BOOLEAN DEFAULT FALSE,
                    processed BOOLEAN DEFAULT FALSE
                );

                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    jti VARCHAR(128) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    revoked_at VARCHAR(64) NOT NULL,
                    expires_at VARCHAR(64)
                );

                CREATE TABLE IF NOT EXISTS login_attempts (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) NOT NULL,
                    ip VARCHAR(64) NOT NULL,
                    attempted_at VARCHAR(64) NOT NULL,
                    success INTEGER NOT NULL
                );

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
                );
                CREATE INDEX IF NOT EXISTS idx_pg_apply_ledger_user_job ON apply_ledger(user_id, job_id);
                CREATE INDEX IF NOT EXISTS idx_pg_apply_ledger_user_fingerprint ON apply_ledger(user_id, job_fingerprint);

                CREATE TABLE IF NOT EXISTS organizations (
                    org_id VARCHAR(64) PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    slug VARCHAR(255) UNIQUE NOT NULL,
                    owner_id VARCHAR(64) NOT NULL,
                    plan_tier VARCHAR(64) DEFAULT 'FREE',
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_organizations_slug ON organizations(slug);
                CREATE INDEX IF NOT EXISTS idx_pg_organizations_owner_id ON organizations(owner_id);

                CREATE TABLE IF NOT EXISTS memberships (
                    membership_id VARCHAR(64) PRIMARY KEY,
                    org_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    role VARCHAR(64) NOT NULL DEFAULT 'MEMBER',
                    invited_by VARCHAR(64),
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL,
                    UNIQUE(org_id, user_id)
                );
                CREATE INDEX IF NOT EXISTS idx_pg_memberships_user_id ON memberships(user_id);
                CREATE INDEX IF NOT EXISTS idx_pg_memberships_org_id ON memberships(org_id);

                CREATE TABLE IF NOT EXISTS admin_audit_logs (
                    log_id VARCHAR(64) PRIMARY KEY,
                    admin_id VARCHAR(64) NOT NULL,
                    action VARCHAR(128) NOT NULL,
                    target_user_id VARCHAR(64),
                    target_org_id VARCHAR(64),
                    ip_address VARCHAR(64),
                    details JSONB DEFAULT '{}',
                    created_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_admin_audit_logs_admin_id ON admin_audit_logs(admin_id);

                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key VARCHAR(128) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL DEFAULT 'default',
                    method VARCHAR(16) NOT NULL,
                    path VARCHAR(512) NOT NULL,
                    request_hash VARCHAR(64) NOT NULL,
                    status_code INTEGER,
                    response_headers JSONB,
                    response_body TEXT,
                    status VARCHAR(32) NOT NULL,
                    created_at VARCHAR(64) NOT NULL,
                    expires_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_idempotency_keys_expires ON idempotency_keys(expires_at);
                CREATE INDEX IF NOT EXISTS idx_pg_idempotency_keys_user ON idempotency_keys(user_id, idempotency_key);

                -- Epic F: MFA Credentials Table
                CREATE TABLE IF NOT EXISTS mfa_credentials (
                    user_id VARCHAR(64) PRIMARY KEY,
                    secret TEXT NOT NULL,
                    backup_codes JSONB NOT NULL,
                    is_enabled BOOLEAN NOT NULL DEFAULT FALSE,
                    created_at VARCHAR(64) NOT NULL,
                    updated_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_mfa_credentials_user ON mfa_credentials(user_id);

                -- Epic F: User Sessions Table
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    token_jti VARCHAR(64) NOT NULL,
                    ip_address VARCHAR(64),
                    user_agent TEXT,
                    device_name VARCHAR(128),
                    created_at VARCHAR(64) NOT NULL,
                    last_active VARCHAR(64) NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT TRUE
                );
                CREATE INDEX IF NOT EXISTS idx_pg_user_sessions_user ON user_sessions(user_id, is_active);
                CREATE INDEX IF NOT EXISTS idx_pg_user_sessions_jti ON user_sessions(token_jti);

                -- Epic F: Security Audit Logs Table (Append-Only)
                CREATE TABLE IF NOT EXISTS security_audit_logs (
                    log_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64),
                    event_type VARCHAR(128) NOT NULL,
                    severity VARCHAR(32) NOT NULL DEFAULT 'INFO',
                    ip_address VARCHAR(64),
                    user_agent TEXT,
                    details JSONB DEFAULT '{}',
                    created_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_sec_audit_user ON security_audit_logs(user_id);
                CREATE INDEX IF NOT EXISTS idx_pg_sec_audit_event ON security_audit_logs(event_type);
                CREATE INDEX IF NOT EXISTS idx_pg_sec_audit_severity ON security_audit_logs(severity);
                CREATE INDEX IF NOT EXISTS idx_pg_sec_audit_created ON security_audit_logs(created_at DESC);

                -- Epic H: Analytics Events Warehouse Table
                CREATE TABLE IF NOT EXISTS analytics_events (
                    event_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    event_type VARCHAR(64) NOT NULL,
                    entity_type VARCHAR(64) NOT NULL,
                    entity_id VARCHAR(64) NOT NULL,
                    properties JSONB NOT NULL DEFAULT '{}',
                    created_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_analytics_events_user_type_date ON analytics_events(user_id, event_type, created_at);

                -- Epic H: A/B Testing Experiments Table
                CREATE TABLE IF NOT EXISTS ab_experiments (
                    experiment_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    name VARCHAR(128) NOT NULL,
                    description TEXT,
                    variants JSONB NOT NULL DEFAULT '[]',
                    status VARCHAR(32) DEFAULT 'ACTIVE',
                    created_at VARCHAR(64) NOT NULL,
                    ended_at VARCHAR(64)
                );
                CREATE INDEX IF NOT EXISTS idx_pg_ab_experiments_user ON ab_experiments(user_id, status);

                -- Epic H: A/B Testing Assignments Table
                CREATE TABLE IF NOT EXISTS ab_assignments (
                    assignment_id VARCHAR(64) PRIMARY KEY,
                    experiment_id VARCHAR(64) NOT NULL,
                    user_id VARCHAR(64) NOT NULL,
                    entity_id VARCHAR(64) NOT NULL,
                    variant VARCHAR(64) NOT NULL,
                    converted BOOLEAN DEFAULT FALSE,
                    converted_at VARCHAR(64),
                    assigned_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_ab_assignments_exp_user_entity ON ab_assignments(experiment_id, user_id, entity_id);

                -- Epic H: Conversion Signals & Dynamic Weights Table
                CREATE TABLE IF NOT EXISTS conversion_signals (
                    signal_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    feature_type VARCHAR(32) NOT NULL,
                    feature_key VARCHAR(128) NOT NULL,
                    sample_count INTEGER DEFAULT 0,
                    callback_count INTEGER DEFAULT 0,
                    conversion_rate FLOAT DEFAULT 0.0,
                    weight_multiplier FLOAT DEFAULT 1.0,
                    updated_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_conv_signals_user_feat ON conversion_signals(user_id, feature_type, feature_key);

                -- Epic J: User Consents Audit Table
                CREATE TABLE IF NOT EXISTS user_consents (
                    consent_id VARCHAR(64) PRIMARY KEY,
                    user_id VARCHAR(64) NOT NULL,
                    consent_type VARCHAR(64) NOT NULL,
                    version VARCHAR(32) NOT NULL DEFAULT '1.0',
                    consented BOOLEAN NOT NULL DEFAULT TRUE,
                    ip_address VARCHAR(64),
                    user_agent TEXT,
                    created_at VARCHAR(64) NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_pg_user_consents_user_type ON user_consents(user_id, consent_type);
                CREATE INDEX IF NOT EXISTS idx_pg_user_consents_user_created ON user_consents(user_id, created_at);

                -- High-traffic compound indexes for query tuning
                CREATE INDEX IF NOT EXISTS idx_pg_emails_user_received ON emails(user_id, received_at DESC);
                CREATE INDEX IF NOT EXISTS idx_pg_hitl_user_status ON hitl_events(user_id, status);
                CREATE INDEX IF NOT EXISTS idx_pg_outreach_user_job ON outreach_records(user_id, job_id);
                CREATE INDEX IF NOT EXISTS idx_pg_jobs_user_applied ON jobs(user_id, applied_at DESC);
                """)
                conn.commit()
        finally:
            self.release_connection(conn)

    # User Auth Operations
    def create_user(self, user: User) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO users (user_id, email, password_hash, full_name, role, is_active, email_verified, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (email) DO NOTHING
                """, (
                    user.user_id, user.email.lower().strip(), user.password_hash,
                    user.full_name, user.role.value if hasattr(user.role, 'value') else str(user.role),
                    user.is_active, user.email_verified, user.created_at, user.updated_at
                ))
                conn.commit()
                return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def get_user_by_email(self, email: str) -> Optional[User]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id, email, password_hash, full_name, role, is_active, email_verified, created_at, updated_at FROM users WHERE email = %s", (email.lower().strip(),))
                row = cursor.fetchone()
                if not row: return None
                return User(user_id=row[0], email=row[1], password_hash=row[2], full_name=row[3], role=row[4], is_active=row[5], email_verified=row[6], created_at=row[7], updated_at=row[8])
        finally:
            self.release_connection(conn)

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT user_id, email, password_hash, full_name, role, is_active, email_verified, created_at, updated_at FROM users WHERE user_id = %s", (user_id,))
                row = cursor.fetchone()
                if not row: return None
                if len(row) >= 9:
                    return User(user_id=row[0], email=row[1], password_hash=row[2], full_name=row[3], role=row[4], is_active=row[5], email_verified=row[6], created_at=row[7], updated_at=row[8])
                return User(user_id=row[0], email=row[1], password_hash="", full_name=row[2] if len(row) > 2 else "", role=row[3] if len(row) > 3 else "FREE", is_active=bool(row[4]) if len(row) > 4 else True, email_verified=bool(row[5]) if len(row) > 5 else False, created_at=row[6] if len(row) > 6 else "", updated_at=row[7] if len(row) > 7 else "")
        finally:
            self.release_connection(conn)

    # Candidate Profile Operations (PII Encrypted)
    def save_profile(self, profile: CandidateProfile, user_id: str) -> bool:
        from app.core.database import DatabaseManager
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                target_id = profile.id or user_id
                enc_dict = DatabaseManager._encrypt_profile_dict(profile.dict())
                cursor.execute("""
                INSERT INTO profiles (id, user_id, data, updated_at)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (id) DO UPDATE SET data = EXCLUDED.data, updated_at = EXCLUDED.updated_at
                """, (target_id, user_id, json.dumps(enc_dict), profile.updated_at))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_profile(self, user_id: str, profile_id: Optional[str] = None) -> Optional[CandidateProfile]:
        from app.core.database import DatabaseManager
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if profile_id:
                    cursor.execute("SELECT data FROM profiles WHERE user_id = %s AND id = %s ORDER BY updated_at DESC LIMIT 1", (user_id, profile_id))
                else:
                    cursor.execute("SELECT data FROM profiles WHERE user_id = %s ORDER BY updated_at DESC LIMIT 1", (user_id,))
                row = cursor.fetchone()
                if row:
                    try:
                        raw_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                        dec_data = DatabaseManager._decrypt_profile_dict(raw_data)
                        return CandidateProfile(**dec_data)
                    except Exception:
                        return None
                return None
        finally:
            self.release_connection(conn)

    # Vault Operations
    def save_vault_entry(self, entry: VaultEntry, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO vault (qa_id, user_id, slot_type, slot_key, question_pattern, embedding, answer_template, dynamic_variables, usage_count, last_used_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (qa_id) DO UPDATE SET answer_template = EXCLUDED.answer_template, usage_count = EXCLUDED.usage_count, last_used_at = EXCLUDED.last_used_at
                """, (
                    entry.qa_id, user_id, entry.slot_type.value if hasattr(entry.slot_type, 'value') else str(entry.slot_type),
                    entry.slot_key, entry.question_pattern, json.dumps(entry.embedding), entry.answer_template,
                    json.dumps(entry.dynamic_variables), entry.usage_count, entry.last_used_at, entry.created_at
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_vault_entries(self, user_id: str) -> List[VaultEntry]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT qa_id, user_id, slot_type, slot_key, question_pattern, embedding, answer_template, dynamic_variables, usage_count, last_used_at, created_at FROM vault WHERE user_id = %s", (user_id,))
                rows = cursor.fetchall()
                entries = []
                for r in rows:
                    entries.append(VaultEntry(
                        qa_id=r[0], user_id=r[1], slot_type=r[2], slot_key=r[3], question_pattern=r[4],
                        embedding=r[5] if isinstance(r[5], list) else json.loads(r[5]),
                        answer_template=r[6],
                        dynamic_variables=r[7] if isinstance(r[7], list) else json.loads(r[7]),
                        usage_count=r[8], last_used_at=r[9], created_at=r[10]
                    ))
                return entries
        finally:
            self.release_connection(conn)

    # Job Listing Operations
    def save_job(self, job: JobListing, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                notes_to_save = job.notes or ""
                meta_payload = {}
                if getattr(job, "interview_date", None):
                    meta_payload["interview_date"] = job.interview_date
                if getattr(job, "created_at", None):
                    meta_payload["created_at"] = job.created_at

                if meta_payload:
                    meta_str = json.dumps(meta_payload)
                    if notes_to_save:
                        notes_to_save = f"{notes_to_save}\n__meta__:{meta_str}"
                    else:
                        notes_to_save = f"__meta__:{meta_str}"

                cursor.execute("""
                INSERT INTO jobs (job_id, user_id, fingerprint, platform, company, title, location, url, description, salary_range, seniority_level, posted_date, match_score, priority_score, match_reasons, missing_skills, status, submission_mode, applied_at, application_id, confirmation_screenshot_path, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET status = EXCLUDED.status, applied_at = EXCLUDED.applied_at, notes = EXCLUDED.notes
                """, (
                    job.job_id, user_id, job.fingerprint, job.platform, job.company, job.title, job.location,
                    job.url, job.description, job.salary_range, job.seniority_level, job.posted_date,
                    job.match_score, job.priority_score, json.dumps(job.match_reasons), json.dumps(job.missing_skills),
                    job.status.value if hasattr(job.status, 'value') else str(job.status),
                    job.submission_mode, job.applied_at, job.application_id, job.confirmation_screenshot_path, notes_to_save
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_jobs(self, user_id: str, status: Optional[ApplicationStatus] = None) -> List[JobListing]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if status:
                    status_str = status.value if hasattr(status, 'value') else str(status)
                    cursor.execute("SELECT job_id, user_id, fingerprint, platform, company, title, location, url, description, salary_range, seniority_level, posted_date, match_score, priority_score, match_reasons, missing_skills, status, submission_mode, applied_at, application_id, confirmation_screenshot_path, notes FROM jobs WHERE user_id = %s AND status = %s", (user_id, status_str))
                else:
                    cursor.execute("SELECT job_id, user_id, fingerprint, platform, company, title, location, url, description, salary_range, seniority_level, posted_date, match_score, priority_score, match_reasons, missing_skills, status, submission_mode, applied_at, application_id, confirmation_screenshot_path, notes FROM jobs WHERE user_id = %s", (user_id,))
                rows = cursor.fetchall()
                jobs = []
                for r in rows:
                    raw_notes = r[21] or ""
                    extracted_interview_date = None
                    extracted_created_at = None
                    clean_notes = raw_notes

                    if raw_notes and "__meta__:" in raw_notes:
                        parts = raw_notes.split("\n__meta__:" if "\n__meta__:" in raw_notes else "__meta__:")
                        clean_notes = parts[0].strip() if parts[0].strip() else None
                        try:
                            meta_dict = json.loads(parts[1])
                            extracted_interview_date = meta_dict.get("interview_date")
                            extracted_created_at = meta_dict.get("created_at")
                        except Exception:
                            clean_notes = raw_notes
                    elif not raw_notes:
                        clean_notes = None

                    jobs.append(JobListing(
                        job_id=r[0], user_id=r[1], fingerprint=r[2], platform=r[3], company=r[4], title=r[5], location=r[6],
                        url=r[7], description=r[8], salary_range=r[9], seniority_level=r[10], posted_date=r[11],
                        match_score=float(r[12] or 0), priority_score=float(r[13] or 0),
                        match_reasons=r[14] if isinstance(r[14], list) else json.loads(r[14] or '[]'),
                        missing_skills=r[15] if isinstance(r[15], list) else json.loads(r[15] or '[]'),
                        status=ApplicationStatus(r[16]), submission_mode=r[17], applied_at=r[18],
                        created_at=extracted_created_at, interview_date=extracted_interview_date,
                        application_id=r[19], confirmation_screenshot_path=r[20], notes=clean_notes
                    ))
                return jobs
        finally:
            self.release_connection(conn)

    def get_job_by_id(self, job_id: str, user_id: str) -> Optional[JobListing]:
        jobs = self.get_jobs(user_id=user_id)
        for j in jobs:
            if j.job_id == job_id:
                return j
        return None

    def save_hitl_event(self, event: HITLEvent, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO hitl_events (event_id, user_id, job_id, company, role_title, question_text, input_type, options, ai_suggested_draft, user_answer, status, screenshot_path, dom_snapshot, field_selector, created_at, resolved_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET user_answer = EXCLUDED.user_answer, status = EXCLUDED.status, resolved_at = EXCLUDED.resolved_at
                """, (
                    event.event_id, user_id, event.job_id, event.company, event.role_title, event.question_text,
                    event.input_type, json.dumps(event.options), event.ai_suggested_draft, event.user_answer,
                    event.status, event.screenshot_path, event.dom_snapshot, event.field_selector,
                    event.created_at, event.resolved_at
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_pending_hitl(self, user_id: str) -> List[HITLEvent]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT event_id, user_id, job_id, company, role_title, question_text, input_type, options, ai_suggested_draft, user_answer, status, screenshot_path, dom_snapshot, field_selector, created_at, resolved_at FROM hitl_events WHERE user_id = %s AND status = 'PENDING'", (user_id,))
                rows = cursor.fetchall()
                events = []
                for r in rows:
                    if len(r) >= 16:
                        events.append(HITLEvent(
                            event_id=r[0], user_id=r[1], job_id=r[2], company=r[3], role_title=r[4],
                            question_text=r[5], input_type=r[6],
                            options=r[7] if isinstance(r[7], list) else json.loads(r[7] or '[]'),
                            ai_suggested_draft=r[8], user_answer=r[9], status=r[10],
                            screenshot_path=r[11], dom_snapshot=r[12], field_selector=r[13],
                            created_at=r[14], resolved_at=r[15]
                        ))
                    else:
                        events.append(HITLEvent(
                            event_id=r[0], user_id=r[1], job_id=r[2], company=r[3], role_title=r[4],
                            question_text=r[5], input_type=r[6],
                            options=r[7] if isinstance(r[7], list) else json.loads(r[7] or '[]'),
                            ai_suggested_draft=r[8], user_answer=r[9], status=r[10],
                            created_at=r[11], resolved_at=r[12] if len(r) > 12 else None
                        ))
                return events
        finally:
            self.release_connection(conn)

    def save_email(self, email: EmailMessage, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO emails (message_id, user_id, sender, recipient, subject, body_text, received_at, associated_job_id, intent, scheduling_links, has_tracking_pixels, processed)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (message_id) DO NOTHING
                """, (
                    email.message_id, user_id, email.sender, email.recipient, email.subject,
                    email.body_text, email.received_at, email.associated_job_id,
                    email.intent.value if hasattr(email.intent, 'value') else str(email.intent),
                    json.dumps(email.scheduling_links), email.has_tracking_pixels, email.processed
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_emails(self, user_id: str) -> List[EmailMessage]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT message_id, user_id, sender, recipient, subject, body_text, received_at, associated_job_id, intent, scheduling_links, has_tracking_pixels, processed FROM emails WHERE user_id = %s ORDER BY received_at DESC", (user_id,))
                rows = cursor.fetchall()
                emails = []
                for r in rows:
                    emails.append(EmailMessage(
                        message_id=r[0], user_id=r[1], sender=r[2], recipient=r[3], subject=r[4],
                        body_text=r[5], received_at=r[6], associated_job_id=r[7], intent=r[8],
                        scheduling_links=r[9] if isinstance(r[9], list) else json.loads(r[9] or '[]'),
                        has_tracking_pixels=bool(r[10]), processed=bool(r[11])
                    ))
                return emails
        finally:
            self.release_connection(conn)

    def save_outreach(self, record: OutreachRecord, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO outreach_records (outreach_id, user_id, job_id, channel, recipient_name, recipient_title, recipient_contact, message_content, status, sent_at, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (outreach_id) DO UPDATE SET status = EXCLUDED.status, sent_at = EXCLUDED.sent_at
                """, (
                    record.outreach_id, user_id, record.job_id,
                    record.channel.value if hasattr(record.channel, 'value') else str(record.channel),
                    record.recipient_name, record.recipient_title, record.recipient_contact,
                    record.message_content, record.status, record.sent_at, record.created_at
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_outreach(self, job_id: str, user_id: str) -> List[OutreachRecord]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT outreach_id, user_id, job_id, channel, recipient_name, recipient_title, recipient_contact, message_content, status, sent_at, created_at FROM outreach_records WHERE user_id = %s AND job_id = %s", (user_id, job_id))
                rows = cursor.fetchall()
                records = []
                for r in rows:
                    records.append(OutreachRecord(
                        outreach_id=r[0], user_id=r[1], job_id=r[2], channel=r[3],
                        recipient_name=r[4], recipient_title=r[5], recipient_contact=r[6],
                        message_content=r[7], status=r[8], sent_at=r[9], created_at=r[10]
                    ))
                return records
        finally:
            self.release_connection(conn)

    def get_funnel_metrics(self, user_id: str) -> Dict[str, Any]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM jobs WHERE user_id = %s", (user_id,))
                total_sourced = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM jobs WHERE user_id = %s AND status IN ('SUBMITTED', 'RESPONDED', 'INTERVIEW', 'OFFER')", (user_id,))
                total_applied = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM jobs WHERE user_id = %s AND status = 'INTERVIEW'", (user_id,))
                interviews = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM jobs WHERE user_id = %s AND status = 'OFFER'", (user_id,))
                offers = cursor.fetchone()[0]

                cursor.execute("SELECT COUNT(*) FROM emails WHERE user_id = %s AND intent IN ('INTERVIEW_INVITE', 'ASSESSMENT')", (user_id,))
                recruiter_responses = cursor.fetchone()[0]

                response_rate = (recruiter_responses / total_applied * 100) if total_applied > 0 else 0.0

                return {
                    "total_sourced": total_sourced,
                    "total_applied": total_applied,
                    "interviews_count": interviews,
                    "offers_count": offers,
                    "recruiter_responses": recruiter_responses,
                    "response_rate_percent": round(response_rate, 2)
                }
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Apply Ledger Operations (PostgreSQL Multi-Tenant)
    # =========================================================================
    def save_apply_ledger_entry(self, entry: ApplyLedgerEntry, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO apply_ledger (
                    ledger_id, user_id, job_id, job_fingerprint, status,
                    attempt_count, max_retries, last_error_category, last_error_message,
                    confirmation_id, screenshot_path, idempotency_key, created_at, updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (ledger_id) DO UPDATE SET
                    status = EXCLUDED.status,
                    attempt_count = EXCLUDED.attempt_count,
                    last_error_category = EXCLUDED.last_error_category,
                    last_error_message = EXCLUDED.last_error_message,
                    confirmation_id = EXCLUDED.confirmation_id,
                    screenshot_path = EXCLUDED.screenshot_path,
                    updated_at = EXCLUDED.updated_at
                """, (
                    entry.ledger_id, user_id, entry.job_id, entry.job_fingerprint,
                    entry.status.value if hasattr(entry.status, "value") else str(entry.status),
                    entry.attempt_count, entry.max_retries, entry.last_error_category,
                    entry.last_error_message, entry.confirmation_id, entry.screenshot_path,
                    entry.idempotency_key, entry.created_at, entry.updated_at
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def _row_to_apply_ledger(self, r: Any) -> ApplyLedgerEntry:
        status_val = ApplyLedgerStatus.INITIATED
        for st in ApplyLedgerStatus:
            if st.value == r[4]:
                status_val = st
                break
        return ApplyLedgerEntry(
            ledger_id=r[0], user_id=r[1], job_id=r[2], job_fingerprint=r[3],
            status=status_val, attempt_count=r[5], max_retries=r[6],
            last_error_category=r[7], last_error_message=r[8],
            confirmation_id=r[9], screenshot_path=r[10], idempotency_key=r[11],
            created_at=r[12], updated_at=r[13]
        )

    def get_apply_ledger_entry(self, ledger_id: str, user_id: str) -> Optional[ApplyLedgerEntry]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ledger_id, user_id, job_id, job_fingerprint, status, attempt_count, max_retries, last_error_category, last_error_message, confirmation_id, screenshot_path, idempotency_key, created_at, updated_at FROM apply_ledger WHERE ledger_id = %s AND user_id = %s", (ledger_id, user_id))
                row = cursor.fetchone()
                return self._row_to_apply_ledger(row) if row else None
        finally:
            self.release_connection(conn)

    def get_active_ledger_by_fingerprint(self, fingerprint: str, user_id: str) -> Optional[ApplyLedgerEntry]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ledger_id, user_id, job_id, job_fingerprint, status, attempt_count, max_retries, last_error_category, last_error_message, confirmation_id, screenshot_path, idempotency_key, created_at, updated_at FROM apply_ledger WHERE job_fingerprint = %s AND user_id = %s ORDER BY updated_at DESC LIMIT 1", (fingerprint, user_id))
                row = cursor.fetchone()
                return self._row_to_apply_ledger(row) if row else None
        finally:
            self.release_connection(conn)

    def get_ledger_for_job(self, job_id: str, user_id: str) -> Optional[ApplyLedgerEntry]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT ledger_id, user_id, job_id, job_fingerprint, status, attempt_count, max_retries, last_error_category, last_error_message, confirmation_id, screenshot_path, idempotency_key, created_at, updated_at FROM apply_ledger WHERE job_id = %s AND user_id = %s ORDER BY updated_at DESC LIMIT 1", (job_id, user_id))
                row = cursor.fetchone()
                return self._row_to_apply_ledger(row) if row else None
        finally:
            self.release_connection(conn)

    def list_user_apply_ledger(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[ApplyLedgerEntry]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = "SELECT ledger_id, user_id, job_id, job_fingerprint, status, attempt_count, max_retries, last_error_category, last_error_message, confirmation_id, screenshot_path, idempotency_key, created_at, updated_at FROM apply_ledger WHERE user_id = %s"
                params: list = [user_id]
                if status:
                    query += " AND status = %s"
                    params.append(status)
                query += " ORDER BY updated_at DESC LIMIT %s OFFSET %s"
                params.extend([limit, offset])
                cursor.execute(query, params)
                rows = cursor.fetchall()
                return [self._row_to_apply_ledger(r) for r in rows]
        finally:
            self.release_connection(conn)

    # SaaS Organization & Team Management
    def create_organization(self, org: Organization) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO organizations (org_id, name, slug, owner_id, plan_tier, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (
                    org.org_id, org.name, org.slug.lower().strip(),
                    org.owner_id, org.plan_tier, org.created_at, org.updated_at
                ))
                conn.commit()
                return True
        except Exception:
            return False
        finally:
            self.release_connection(conn)

    def get_organization(self, org_id: str) -> Optional[Organization]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT org_id, name, slug, owner_id, plan_tier, created_at, updated_at FROM organizations WHERE org_id = %s", (org_id,))
                row = cursor.fetchone()
                if not row:
                    return None
                return Organization(
                    org_id=row[0], name=row[1], slug=row[2],
                    owner_id=row[3], plan_tier=row[4], created_at=row[5], updated_at=row[6]
                )
        finally:
            self.release_connection(conn)

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT org_id, name, slug, owner_id, plan_tier, created_at, updated_at FROM organizations WHERE slug = %s", (slug.lower().strip(),))
                row = cursor.fetchone()
                if not row:
                    return None
                return Organization(
                    org_id=row[0], name=row[1], slug=row[2],
                    owner_id=row[3], plan_tier=row[4], created_at=row[5], updated_at=row[6]
                )
        finally:
            self.release_connection(conn)

    def list_user_organizations(self, user_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                SELECT o.org_id, o.name, o.slug, o.owner_id, o.plan_tier, o.created_at, m.role
                FROM organizations o
                JOIN memberships m ON o.org_id = m.org_id
                WHERE m.user_id = %s
                ORDER BY o.created_at DESC
                """, (user_id,))
                rows = cursor.fetchall()
                return [{
                    "org_id": r[0], "name": r[1], "slug": r[2],
                    "owner_id": r[3], "plan_tier": r[4], "created_at": r[5], "role": r[6]
                } for r in rows]
        finally:
            self.release_connection(conn)

    def update_organization(self, org_id: str, name: Optional[str] = None, plan_tier: Optional[str] = None) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                now_str = datetime.now().isoformat()
                if name is not None and plan_tier is not None:
                    cursor.execute("UPDATE organizations SET name = %s, plan_tier = %s, updated_at = %s WHERE org_id = %s", (name, plan_tier, now_str, org_id))
                elif name is not None:
                    cursor.execute("UPDATE organizations SET name = %s, updated_at = %s WHERE org_id = %s", (name, now_str, org_id))
                elif plan_tier is not None:
                    cursor.execute("UPDATE organizations SET plan_tier = %s, updated_at = %s WHERE org_id = %s", (plan_tier, now_str, org_id))
                else:
                    return True
                conn.commit()
                return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def add_membership(self, membership: Membership) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO memberships (membership_id, org_id, user_id, role, invited_by, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (org_id, user_id) DO UPDATE SET
                    role = EXCLUDED.role,
                    updated_at = EXCLUDED.updated_at
                """, (
                    membership.membership_id, membership.org_id, membership.user_id,
                    membership.role.value if hasattr(membership.role, 'value') else str(membership.role),
                    membership.invited_by, membership.created_at, membership.updated_at
                ))
                conn.commit()
                return True
        except Exception:
            return False
        finally:
            self.release_connection(conn)

    def get_membership(self, org_id: str, user_id: str) -> Optional[Membership]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT membership_id, org_id, user_id, role, invited_by, created_at, updated_at FROM memberships WHERE org_id = %s AND user_id = %s", (org_id, user_id))
                row = cursor.fetchone()
                if not row:
                    return None
                return Membership(
                    membership_id=row[0], org_id=row[1], user_id=row[2],
                    role=OrgRole(row[3]), invited_by=row[4], created_at=row[5], updated_at=row[6]
                )
        finally:
            self.release_connection(conn)

    def list_org_members(self, org_id: str) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                SELECT m.membership_id, m.org_id, m.user_id, u.email, u.full_name, m.role, m.created_at
                FROM memberships m
                JOIN users u ON m.user_id = u.user_id
                WHERE m.org_id = %s
                ORDER BY m.created_at ASC
                """, (org_id,))
                rows = cursor.fetchall()
                return [{
                    "membership_id": r[0], "org_id": r[1], "user_id": r[2],
                    "email": r[3], "full_name": r[4], "role": r[5], "created_at": r[6]
                } for r in rows]
        finally:
            self.release_connection(conn)

    def remove_membership(self, org_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM memberships WHERE org_id = %s AND user_id = %s", (org_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def update_member_role(self, org_id: str, user_id: str, role: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("UPDATE memberships SET role = %s, updated_at = %s WHERE org_id = %s AND user_id = %s", (role, datetime.now().isoformat(), org_id, user_id))
                conn.commit()
                return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def log_admin_action(self, log_entry: AdminAuditLog) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO admin_audit_logs (log_id, admin_id, action, target_user_id, target_org_id, ip_address, details, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    log_entry.log_id, log_entry.admin_id, log_entry.action,
                    log_entry.target_user_id, log_entry.target_org_id,
                    log_entry.ip_address, json.dumps(log_entry.details), log_entry.created_at
                ))
                conn.commit()
                return True
        except Exception:
            return False
        finally:
            self.release_connection(conn)

    def list_admin_audit_logs(self, limit: int = 50, offset: int = 0) -> List[AdminAuditLog]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT log_id, admin_id, action, target_user_id, target_org_id, ip_address, details, created_at FROM admin_audit_logs ORDER BY created_at DESC LIMIT %s OFFSET %s", (limit, offset))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    details = r[6] if isinstance(r[6], dict) else (json.loads(r[6]) if r[6] else {})
                    results.append(AdminAuditLog(
                        log_id=r[0], admin_id=r[1], action=r[2],
                        target_user_id=r[3], target_org_id=r[4],
                        ip_address=r[5], details=details, created_at=r[7]
                    ))
                return results
        finally:
            self.release_connection(conn)

    def list_all_users(self, limit: int = 50, offset: int = 0, search: Optional[str] = None) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if search:
                    term = f"%{search.lower().strip()}%"
                    cursor.execute("""
                    SELECT user_id, email, full_name, role, is_active, email_verified, created_at, updated_at
                    FROM users
                    WHERE LOWER(email) LIKE %s OR LOWER(full_name) LIKE %s
                    ORDER BY created_at DESC LIMIT %s OFFSET %s
                    """, (term, term, limit, offset))
                else:
                    cursor.execute("""
                    SELECT user_id, email, full_name, role, is_active, email_verified, created_at, updated_at
                    FROM users
                    ORDER BY created_at DESC LIMIT %s OFFSET %s
                    """, (limit, offset))
                rows = cursor.fetchall()
                return [{
                    "user_id": r[0], "email": r[1], "full_name": r[2], "role": r[3],
                    "is_active": r[4], "email_verified": r[5], "created_at": r[6], "updated_at": r[7]
                } for r in rows]
        finally:
            self.release_connection(conn)

    def count_all_users(self, search: Optional[str] = None) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if search:
                    term = f"%{search.lower().strip()}%"
                    cursor.execute("SELECT COUNT(*) FROM users WHERE LOWER(email) LIKE %s OR LOWER(full_name) LIKE %s", (term, term))
                else:
                    cursor.execute("SELECT COUNT(*) FROM users")
                row = cursor.fetchone()
                return row[0] if row else 0
        finally:
            self.release_connection(conn)

    def list_all_organizations(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                SELECT o.org_id, o.name, o.slug, o.owner_id, o.plan_tier, o.created_at,
                       COUNT(m.user_id) as member_count
                FROM organizations o
                LEFT JOIN memberships m ON o.org_id = m.org_id
                GROUP BY o.org_id, o.name, o.slug, o.owner_id, o.plan_tier, o.created_at
                ORDER BY o.created_at DESC LIMIT %s OFFSET %s
                """, (limit, offset))
                rows = cursor.fetchall()
                return [{
                    "org_id": r[0], "name": r[1], "slug": r[2], "owner_id": r[3],
                    "plan_tier": r[4], "created_at": r[5], "member_count": r[6]
                } for r in rows]
        finally:
            self.release_connection(conn)

    def count_all_organizations(self) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM organizations")
                row = cursor.fetchone()
                return row[0] if row else 0
        finally:
            self.release_connection(conn)

    def get_admin_system_metrics(self) -> Dict[str, Any]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT COUNT(*) FROM users")
                total_users = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM jobs")
                total_jobs = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM apply_ledger WHERE status = 'SUBMITTED'")
                total_applications = cursor.fetchone()[0]
                cursor.execute("SELECT COUNT(*) FROM organizations")
                total_organizations = cursor.fetchone()[0]
                cursor.execute("SELECT role, COUNT(*) FROM users GROUP BY role")
                active_subscriptions = {"FREE": 0, "PRO": 0, "ELITE": 0, "ADMIN": 0}
                for row in cursor.fetchall():
                    if row[0] in active_subscriptions:
                        active_subscriptions[row[0]] = row[1]
                return {
                    "total_users": total_users,
                    "total_jobs": total_jobs,
                    "total_applications": total_applications,
                    "active_subscriptions": active_subscriptions,
                    "total_organizations": total_organizations
                }
        finally:
            self.release_connection(conn)

    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        return {
            "user_id": user_id,
            "exported_at": datetime.now().isoformat(),
            "account": self.get_user_by_id(user_id).dict() if self.get_user_by_id(user_id) else {},
            "profile": self.get_profile(user_id).dict() if self.get_profile(user_id) else {},
            "jobs": [j.dict() for j in self.get_jobs(user_id)],
            "knowledge_vault": [v.dict() for v in self.get_vault_entries(user_id)],
            "apply_ledger": [l.dict() for l in self.list_user_apply_ledger(user_id, limit=10000)],
            "emails": [e.dict() for e in self.get_emails(user_id)],
            "organizations": self.list_user_organizations(user_id)
        }

    def hard_delete_user_account(self, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM users WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM profiles WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM jobs WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM vault WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM apply_ledger WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM hitl_events WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM emails WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM outreach_records WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM memberships WHERE user_id = %s", (user_id,))
                cursor.execute("DELETE FROM organizations WHERE owner_id = %s", (user_id,))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    # Idempotency Engine Operations
    def save_idempotency_record(self, record: Dict[str, Any]) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO idempotency_keys (
                    idempotency_key, user_id, method, path, request_hash,
                    status_code, response_headers, response_body, status, created_at, expires_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (idempotency_key) DO UPDATE SET
                    status_code = EXCLUDED.status_code,
                    response_headers = EXCLUDED.response_headers,
                    response_body = EXCLUDED.response_body,
                    status = EXCLUDED.status,
                    expires_at = EXCLUDED.expires_at
                """, (
                    record["idempotency_key"],
                    record.get("user_id", "default"),
                    record["method"],
                    record["path"],
                    record["request_hash"],
                    record.get("status_code"),
                    json.dumps(record.get("response_headers", {})),
                    record.get("response_body"),
                    record.get("status", "PENDING"),
                    record.get("created_at", datetime.now().isoformat()),
                    record.get("expires_at", "")
                ))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def get_idempotency_record(self, idempotency_key: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                SELECT idempotency_key, user_id, method, path, request_hash,
                       status_code, response_headers, response_body, status, created_at, expires_at
                FROM idempotency_keys
                WHERE idempotency_key = %s AND (user_id = %s OR user_id = 'default')
                """, (idempotency_key, user_id))
                row = cursor.fetchone()
                if not row:
                    return None

                headers = row[6] if isinstance(row[6], dict) else (json.loads(row[6]) if row[6] else {})
                return {
                    "idempotency_key": row[0],
                    "user_id": row[1],
                    "method": row[2],
                    "path": row[3],
                    "request_hash": row[4],
                    "status_code": row[5],
                    "response_headers": headers,
                    "response_body": row[7],
                    "status": row[8],
                    "created_at": row[9],
                    "expires_at": row[10]
                }
        finally:
            self.release_connection(conn)

    def update_idempotency_record(
        self,
        idempotency_key: str,
        status: str,
        status_code: int,
        response_headers: Dict[str, Any],
        response_body: str
    ) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                UPDATE idempotency_keys
                SET status = %s, status_code = %s, response_headers = %s, response_body = %s
                WHERE idempotency_key = %s
                """, (status, status_code, json.dumps(response_headers), response_body, idempotency_key))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def delete_idempotency_record(self, idempotency_key: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM idempotency_keys WHERE idempotency_key = %s", (idempotency_key,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def cleanup_expired_idempotency_keys(self) -> int:
        now_iso = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM idempotency_keys WHERE expires_at != '' AND expires_at < %s", (now_iso,))
                conn.commit()
                return cursor.rowcount
        except Exception:
            conn.rollback()
            return 0
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Epic F: MFA / TOTP Storage
    # =========================================================================
    def get_mfa_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT user_id, secret, backup_codes, is_enabled, created_at, updated_at FROM mfa_credentials WHERE user_id = %s",
                    (user_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                backup_codes = []
                if row[2]:
                    try:
                        backup_codes = json.loads(row[2]) if isinstance(row[2], str) else row[2]
                    except Exception:
                        backup_codes = []
                return {
                    "user_id": row[0],
                    "secret": row[1],
                    "backup_codes": backup_codes,
                    "is_enabled": bool(row[3]),
                    "created_at": row[4],
                    "updated_at": row[5]
                }
        finally:
            self.release_connection(conn)

    def save_mfa_credentials(self, user_id: str, secret: str, backup_codes: List[Dict[str, Any]], is_enabled: bool) -> bool:
        now_str = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO mfa_credentials (user_id, secret, backup_codes, is_enabled, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT(user_id) DO UPDATE SET
                    secret = EXCLUDED.secret,
                    backup_codes = EXCLUDED.backup_codes,
                    is_enabled = EXCLUDED.is_enabled,
                    updated_at = EXCLUDED.updated_at
                """, (user_id, secret, json.dumps(backup_codes), is_enabled, now_str, now_str))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def delete_mfa_credentials(self, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("DELETE FROM mfa_credentials WHERE user_id = %s", (user_id,))
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Epic F: Session & Device Management
    # =========================================================================
    def create_session(self, session: Dict[str, Any]) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO user_sessions (session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    session["session_id"],
                    session["user_id"],
                    session["token_jti"],
                    session.get("ip_address"),
                    session.get("user_agent"),
                    session.get("device_name", "Unknown Device"),
                    session.get("created_at", datetime.now().isoformat()),
                    session.get("last_active", datetime.now().isoformat()),
                    session.get("is_active", True)
                ))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active FROM user_sessions WHERE session_id = %s",
                    (session_id,)
                )
                row = cursor.fetchone()
                if not row:
                    return None
                return {
                    "session_id": row[0],
                    "user_id": row[1],
                    "token_jti": row[2],
                    "ip_address": row[3],
                    "user_agent": row[4],
                    "device_name": row[5],
                    "created_at": row[6],
                    "last_active": row[7],
                    "is_active": bool(row[8])
                }
        finally:
            self.release_connection(conn)

    def list_user_sessions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if active_only:
                    cursor.execute(
                        "SELECT session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active FROM user_sessions WHERE user_id = %s AND is_active = TRUE ORDER BY last_active DESC",
                        (user_id,)
                    )
                else:
                    cursor.execute(
                        "SELECT session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active FROM user_sessions WHERE user_id = %s ORDER BY last_active DESC",
                        (user_id,)
                    )
                rows = cursor.fetchall()
                return [
                    {
                        "session_id": r[0],
                        "user_id": r[1],
                        "token_jti": r[2],
                        "ip_address": r[3],
                        "user_agent": r[4],
                        "device_name": r[5],
                        "created_at": r[6],
                        "last_active": r[7],
                        "is_active": bool(r[8])
                    }
                    for r in rows
                ]
        finally:
            self.release_connection(conn)

    def revoke_session(self, session_id: str, user_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_sessions SET is_active = FALSE WHERE session_id = %s AND user_id = %s",
                    (session_id, user_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def revoke_all_user_sessions(self, user_id: str, except_jti: Optional[str] = None) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                if except_jti:
                    cursor.execute(
                        "UPDATE user_sessions SET is_active = FALSE WHERE user_id = %s AND token_jti != %s AND is_active = TRUE",
                        (user_id, except_jti)
                    )
                else:
                    cursor.execute(
                        "UPDATE user_sessions SET is_active = FALSE WHERE user_id = %s AND is_active = TRUE",
                        (user_id,)
                    )
                conn.commit()
                return cursor.rowcount
        except Exception:
            conn.rollback()
            return 0
        finally:
            self.release_connection(conn)

    def update_session_activity(self, token_jti: str) -> bool:
        now_str = datetime.now().isoformat()
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "UPDATE user_sessions SET last_active = %s WHERE token_jti = %s AND is_active = TRUE",
                    (now_str, token_jti)
                )
                conn.commit()
                return cursor.rowcount > 0
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Epic F: Security Audit Logs (Append-Only)
    # =========================================================================
    def insert_security_audit_log(self, log_entry: Dict[str, Any]) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("""
                INSERT INTO security_audit_logs (log_id, user_id, event_type, severity, ip_address, user_agent, details, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    log_entry["log_id"],
                    log_entry.get("user_id"),
                    log_entry["event_type"],
                    log_entry.get("severity", "INFO"),
                    log_entry.get("ip_address"),
                    log_entry.get("user_agent"),
                    json.dumps(log_entry.get("details", {})),
                    log_entry.get("created_at", datetime.now().isoformat())
                ))
                conn.commit()
                return True
        except Exception:
            conn.rollback()
            return False
        finally:
            self.release_connection(conn)

    def list_security_audit_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT log_id, user_id, event_type, severity, ip_address, user_agent, details, created_at "
                    "FROM security_audit_logs "
                    "WHERE (%s IS NULL OR user_id = %s) "
                    "AND (%s IS NULL OR event_type = %s) "
                    "AND (%s IS NULL OR severity = %s) "
                    "ORDER BY created_at DESC LIMIT %s OFFSET %s"
                )
                cursor.execute(query, (user_id, user_id, event_type, event_type, severity, severity, limit, offset))
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    details = {}
                    if r[6]:
                        try:
                            details = json.loads(r[6]) if isinstance(r[6], str) else r[6]
                        except Exception:
                            details = {}
                    results.append({
                        "log_id": r[0],
                        "user_id": r[1],
                        "event_type": r[2],
                        "severity": r[3],
                        "ip_address": r[4],
                        "user_agent": r[5],
                        "details": details,
                        "created_at": r[7]
                    })
                return results
        finally:
            self.release_connection(conn)

    def count_security_audit_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> int:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT COUNT(*) FROM security_audit_logs "
                    "WHERE (%s IS NULL OR user_id = %s) "
                    "AND (%s IS NULL OR event_type = %s) "
                    "AND (%s IS NULL OR severity = %s)"
                )
                cursor.execute(query, (user_id, user_id, event_type, event_type, severity, severity))
                row = cursor.fetchone()
                return row[0] if row else 0
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Epic H: Analytics Warehouse & Event Streaming (PostgreSQL)
    # =========================================================================
    def record_analytics_event(self, event: AnalyticsEvent) -> str:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO analytics_events (event_id, user_id, event_type, entity_type, entity_id, properties, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    (
                        event.event_id,
                        event.user_id,
                        event.event_type,
                        event.entity_type,
                        event.entity_id,
                        json.dumps(event.properties),
                        event.created_at
                    )
                )
                conn.commit()
                return event.event_id
        finally:
            self.release_connection(conn)

    def query_analytics_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AnalyticsEvent]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT event_id, user_id, event_type, entity_type, entity_id, properties, created_at "
                    "FROM analytics_events "
                    "WHERE (user_id = %s OR %s = 'admin') "
                    "AND (%s IS NULL OR event_type = %s) "
                    "ORDER BY created_at DESC LIMIT %s"
                )
                cursor.execute(query, (user_id, user_id, event_type, event_type, limit))
                rows = cursor.fetchall()
                events = []
                for r in rows:
                    props = json.loads(r[5]) if isinstance(r[5], str) else (r[5] or {})
                    events.append(AnalyticsEvent(
                        event_id=r[0],
                        user_id=r[1],
                        event_type=r[2],
                        entity_type=r[3],
                        entity_id=r[4],
                        properties=props,
                        created_at=r[6]
                    ))
                return events
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Epic H: A/B Testing Framework (PostgreSQL)
    # =========================================================================
    def create_ab_experiment(self, experiment: ABExperiment) -> str:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ab_experiments (experiment_id, user_id, name, description, variants, status, created_at, ended_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT (experiment_id) DO UPDATE SET "
                    "name = EXCLUDED.name, description = EXCLUDED.description, "
                    "variants = EXCLUDED.variants, status = EXCLUDED.status, ended_at = EXCLUDED.ended_at",
                    (
                        experiment.experiment_id,
                        experiment.user_id,
                        experiment.name,
                        experiment.description,
                        json.dumps([v.model_dump() if hasattr(v, "model_dump") else v.dict() for v in experiment.variants]),
                        experiment.status,
                        experiment.created_at,
                        experiment.ended_at
                    )
                )
                conn.commit()
                return experiment.experiment_id
        finally:
            self.release_connection(conn)

    def get_ab_experiment(self, experiment_id: str, user_id: str) -> Optional[ABExperiment]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT experiment_id, user_id, name, description, variants, status, created_at, ended_at "
                    "FROM ab_experiments "
                    "WHERE experiment_id = %s AND (user_id = %s OR %s = 'admin')",
                    (experiment_id, user_id, user_id)
                )
                r = cursor.fetchone()
                if not r:
                    return None
                raw_variants = json.loads(r[4]) if isinstance(r[4], str) else (r[4] or [])
                variants = [ABVariant(**v) for v in raw_variants]
                return ABExperiment(
                    experiment_id=r[0],
                    user_id=r[1],
                    name=r[2],
                    description=r[3],
                    variants=variants,
                    status=r[5],
                    created_at=r[6],
                    ended_at=r[7]
                )
        finally:
            self.release_connection(conn)

    def list_ab_experiments(self, user_id: str) -> List[ABExperiment]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT experiment_id, user_id, name, description, variants, status, created_at, ended_at "
                    "FROM ab_experiments "
                    "WHERE user_id = %s OR %s = 'admin' "
                    "ORDER BY created_at DESC",
                    (user_id, user_id)
                )
                rows = cursor.fetchall()
                experiments = []
                for r in rows:
                    raw_variants = json.loads(r[4]) if isinstance(r[4], str) else (r[4] or [])
                    variants = [ABVariant(**v) for v in raw_variants]
                    experiments.append(ABExperiment(
                        experiment_id=r[0],
                        user_id=r[1],
                        name=r[2],
                        description=r[3],
                        variants=variants,
                        status=r[5],
                        created_at=r[6],
                        ended_at=r[7]
                    ))
                return experiments
        finally:
            self.release_connection(conn)

    def assign_ab_variant(self, experiment_id: str, user_id: str, entity_id: str, variant: str) -> ABAssignment:
        existing = self.get_ab_assignment(experiment_id, user_id, entity_id)
        if existing:
            return existing

        assignment = ABAssignment(
            experiment_id=experiment_id,
            user_id=user_id,
            entity_id=entity_id,
            variant=variant,
            converted=False
        )
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO ab_assignments (assignment_id, experiment_id, user_id, entity_id, variant, converted, converted_at, assigned_at) "
                    "VALUES (%s, %s, %s, %s, %s, FALSE, NULL, %s)",
                    (
                        assignment.assignment_id,
                        assignment.experiment_id,
                        assignment.user_id,
                        assignment.entity_id,
                        assignment.variant,
                        assignment.assigned_at
                    )
                )
                conn.commit()
                return assignment
        finally:
            self.release_connection(conn)

    def get_ab_assignment(self, experiment_id: str, user_id: str, entity_id: str) -> Optional[ABAssignment]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT assignment_id, experiment_id, user_id, entity_id, variant, converted, converted_at, assigned_at "
                    "FROM ab_assignments "
                    "WHERE experiment_id = %s AND user_id = %s AND entity_id = %s",
                    (experiment_id, user_id, entity_id)
                )
                r = cursor.fetchone()
                if not r:
                    return None
                return ABAssignment(
                    assignment_id=r[0],
                    experiment_id=r[1],
                    user_id=r[2],
                    entity_id=r[3],
                    variant=r[4],
                    converted=bool(r[5]),
                    converted_at=r[6],
                    assigned_at=r[7]
                )
        finally:
            self.release_connection(conn)

    def record_ab_conversion(self, experiment_id: str, user_id: str, entity_id: str) -> bool:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                now_iso = datetime.now().isoformat()
                cursor.execute(
                    "UPDATE ab_assignments "
                    "SET converted = TRUE, converted_at = %s "
                    "WHERE experiment_id = %s AND user_id = %s AND entity_id = %s AND converted = FALSE",
                    (now_iso, experiment_id, user_id, entity_id)
                )
                conn.commit()
                return cursor.rowcount > 0
        finally:
            self.release_connection(conn)

    def get_ab_experiment_stats(self, experiment_id: str, user_id: str) -> Dict[str, Any]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT variant, COUNT(*), SUM(CASE WHEN converted = TRUE THEN 1 ELSE 0 END) "
                    "FROM ab_assignments "
                    "WHERE experiment_id = %s AND (user_id = %s OR %s = 'admin') "
                    "GROUP BY variant",
                    (experiment_id, user_id, user_id)
                )
                rows = cursor.fetchall()
                variants_stats = {}
                total_samples = 0
                total_conversions = 0
                for r in rows:
                    var_name = r[0]
                    samples = r[1] or 0
                    conversions = r[2] or 0
                    rate = round((conversions / samples * 100), 2) if samples > 0 else 0.0
                    variants_stats[var_name] = {
                        "samples": samples,
                        "conversions": conversions,
                        "conversion_rate_percent": rate
                    }
                    total_samples += samples
                    total_conversions += conversions

                return {
                    "experiment_id": experiment_id,
                    "total_samples": total_samples,
                    "total_conversions": total_conversions,
                    "variants": variants_stats
                }
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Epic H: Conversion Signals & Feedback Loop Weights (PostgreSQL)
    # =========================================================================
    def upsert_conversion_signal(self, signal: ConversionSignal) -> None:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO conversion_signals (signal_id, user_id, feature_type, feature_key, sample_count, callback_count, conversion_rate, weight_multiplier, updated_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) "
                    "ON CONFLICT(signal_id) DO UPDATE SET "
                    "sample_count = EXCLUDED.sample_count, "
                    "callback_count = EXCLUDED.callback_count, "
                    "conversion_rate = EXCLUDED.conversion_rate, "
                    "weight_multiplier = EXCLUDED.weight_multiplier, "
                    "updated_at = EXCLUDED.updated_at",
                    (
                        signal.signal_id,
                        signal.user_id,
                        signal.feature_type,
                        signal.feature_key,
                        signal.sample_count,
                        signal.callback_count,
                        signal.conversion_rate,
                        signal.weight_multiplier,
                        signal.updated_at
                    )
                )
                conn.commit()
        finally:
            self.release_connection(conn)

    def get_conversion_signals(self, user_id: str, feature_type: Optional[str] = None) -> List[ConversionSignal]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                query = (
                    "SELECT signal_id, user_id, feature_type, feature_key, sample_count, callback_count, conversion_rate, weight_multiplier, updated_at "
                    "FROM conversion_signals "
                    "WHERE (user_id = %s OR %s = 'admin') "
                    "AND (%s IS NULL OR feature_type = %s) "
                    "ORDER BY updated_at DESC"
                )
                cursor.execute(query, (user_id, user_id, feature_type, feature_type))
                rows = cursor.fetchall()
                signals = []
                for r in rows:
                    signals.append(ConversionSignal(
                        signal_id=r[0],
                        user_id=r[1],
                        feature_type=r[2],
                        feature_key=r[3],
                        sample_count=r[4],
                        callback_count=r[5],
                        conversion_rate=r[6],
                        weight_multiplier=r[7],
                        updated_at=r[8]
                    ))
                return signals
        finally:
            self.release_connection(conn)

    # =========================================================================
    # Compliance & Consent Management (Epic J)
    # =========================================================================
    def record_user_consent(self, consent: UserConsent) -> bool:
        """Records an append-only user consent decision with audit metadata in PostgreSQL."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                type_val = consent.consent_type.value if hasattr(consent.consent_type, "value") else str(consent.consent_type)
                cursor.execute(
                    "INSERT INTO user_consents (consent_id, user_id, consent_type, version, consented, ip_address, user_agent, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        consent.consent_id,
                        consent.user_id,
                        type_val,
                        consent.version,
                        consent.consented,
                        consent.ip_address,
                        consent.user_agent,
                        consent.created_at
                    )
                )
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_user_consents(self, user_id: str) -> Dict[str, UserConsent]:
        """Returns the active (most recent) consent state for each consent type in PostgreSQL."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT consent_id, user_id, consent_type, version, consented, ip_address, user_agent, created_at "
                    "FROM user_consents WHERE user_id = %s ORDER BY created_at ASC",
                    (user_id,)
                )
                rows = cursor.fetchall()
                consents = {}
                for r in rows:
                    c = UserConsent(
                        consent_id=r[0],
                        user_id=r[1],
                        consent_type=ConsentType(r[2]),
                        version=r[3],
                        consented=bool(r[4]),
                        ip_address=r[5],
                        user_agent=r[6],
                        created_at=r[7]
                    )
                    key = c.consent_type.value if hasattr(c.consent_type, "value") else str(c.consent_type)
                    consents[key] = c
                return consents
        finally:
            self.release_connection(conn)

    def get_user_consent_history(self, user_id: str, consent_type: Optional[str] = None) -> List[UserConsent]:
        """Returns immutable audit trail of consent events for user, optionally filtered by type in PostgreSQL."""
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                type_val = consent_type.value if hasattr(consent_type, "value") else consent_type
                query = (
                    "SELECT consent_id, user_id, consent_type, version, consented, ip_address, user_agent, created_at "
                    "FROM user_consents WHERE user_id = %s "
                    "AND (%s IS NULL OR consent_type = %s) "
                    "ORDER BY created_at DESC"
                )
                cursor.execute(query, (user_id, type_val, type_val))
                rows = cursor.fetchall()
                history = []
                for r in rows:
                    history.append(UserConsent(
                        consent_id=r[0],
                        user_id=r[1],
                        consent_type=ConsentType(r[2]),
                        version=r[3],
                        consented=bool(r[4]),
                        ip_address=r[5],
                        user_agent=r[6],
                        created_at=r[7]
                    ))
                return history
        finally:
            self.release_connection(conn)


