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
    HITLEvent, ApplicationStatus, OutreachRecord, EmailMessage, JobCheckpoint
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
                return User(user_id=row[0], email=row[1], password_hash=row[2], full_name=row[3], role=row[4], is_active=row[5], email_verified=row[6], created_at=row[7], updated_at=row[8])
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
                    raw_data = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    dec_data = DatabaseManager._decrypt_profile_dict(raw_data)
                    return CandidateProfile(**dec_data)
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
                cursor.execute("""
                INSERT INTO jobs (job_id, user_id, fingerprint, platform, company, title, location, url, description, salary_range, seniority_level, posted_date, match_score, priority_score, match_reasons, missing_skills, status, submission_mode, applied_at, application_id, confirmation_screenshot_path, notes)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (job_id) DO UPDATE SET status = EXCLUDED.status, applied_at = EXCLUDED.applied_at, notes = EXCLUDED.notes
                """, (
                    job.job_id, user_id, job.fingerprint, job.platform, job.company, job.title, job.location,
                    job.url, job.description, job.salary_range, job.seniority_level, job.posted_date,
                    job.match_score, job.priority_score, json.dumps(job.match_reasons), json.dumps(job.missing_skills),
                    job.status.value if hasattr(job.status, 'value') else str(job.status),
                    job.submission_mode, job.applied_at, job.application_id, job.confirmation_screenshot_path, job.notes
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
                    jobs.append(JobListing(
                        job_id=r[0], user_id=r[1], fingerprint=r[2], platform=r[3], company=r[4], title=r[5], location=r[6],
                        url=r[7], description=r[8], salary_range=r[9], seniority_level=r[10], posted_date=r[11],
                        match_score=float(r[12] or 0), priority_score=float(r[13] or 0),
                        match_reasons=r[14] if isinstance(r[14], list) else json.loads(r[14] or '[]'),
                        missing_skills=r[15] if isinstance(r[15], list) else json.loads(r[15] or '[]'),
                        status=ApplicationStatus(r[16]), submission_mode=r[17], applied_at=r[18],
                        application_id=r[19], confirmation_screenshot_path=r[20], notes=r[21]
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
                INSERT INTO hitl_events (event_id, user_id, job_id, company, role_title, question_text, input_type, options, ai_suggested_draft, user_answer, status, created_at, resolved_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (event_id) DO UPDATE SET user_answer = EXCLUDED.user_answer, status = EXCLUDED.status, resolved_at = EXCLUDED.resolved_at
                """, (
                    event.event_id, user_id, event.job_id, event.company, event.role_title, event.question_text,
                    event.input_type, json.dumps(event.options), event.ai_suggested_draft, event.user_answer,
                    event.status, event.created_at, event.resolved_at
                ))
                conn.commit()
                return True
        finally:
            self.release_connection(conn)

    def get_pending_hitl(self, user_id: str) -> List[HITLEvent]:
        conn = self.get_connection()
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT event_id, user_id, job_id, company, role_title, question_text, input_type, options, ai_suggested_draft, user_answer, status, created_at, resolved_at FROM hitl_events WHERE user_id = %s AND status = 'PENDING'", (user_id,))
                rows = cursor.fetchall()
                events = []
                for r in rows:
                    events.append(HITLEvent(
                        event_id=r[0], user_id=r[1], job_id=r[2], company=r[3], role_title=r[4],
                        question_text=r[5], input_type=r[6],
                        options=r[7] if isinstance(r[7], list) else json.loads(r[7] or '[]'),
                        ai_suggested_draft=r[8], user_answer=r[9], status=r[10], created_at=r[11], resolved_at=r[12]
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
