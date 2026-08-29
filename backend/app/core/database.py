"""
JobCopilot - SQLite Local-First Storage Engine & Schema Migrator
Configured with Write-Ahead Logging (WAL Mode), Connection Pooling,
Atomic Transactions, and Dynamic Migration Support.
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any
from app.core.config import DB_PATH
from app.core.models import (
    CandidateProfile, VaultEntry, JobListing, HITLEvent,
    ApplicationStatus, OutreachRecord, EmailMessage, JobCheckpoint
)


class DatabaseManager:
    """Thread-safe SQLite Database Manager with WAL mode and atomic migrations."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_pragmas()
        self._run_migrations()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a thread-safe SQLite connection with WAL pragmas."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_pragmas(self):
        with sqlite3.connect(str(self.db_path), timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.commit()

    def _ensure_columns(self, conn: sqlite3.Connection, table_name: str, required_columns: Dict[str, str]):
        """Ensures all required columns exist in the table, adding them if missing."""
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        existing_cols = {row["name"] for row in cursor.fetchall()}
        for col_name, col_type in required_columns.items():
            if col_name not in existing_cols:
                cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type};")

    def _run_migrations(self):
        """Runs incremental schema migrations safely in a single transaction."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS _schema_versions (
                    version INTEGER PRIMARY KEY,
                    applied_at TEXT NOT NULL,
                    description TEXT NOT NULL
                )
                """)
                conn.commit()

                # Profiles Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    data JSON NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)

                # Vault Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault (
                    qa_id TEXT PRIMARY KEY,
                    slot_type TEXT NOT NULL,
                    slot_key TEXT NOT NULL,
                    question_pattern TEXT NOT NULL,
                    embedding JSON NOT NULL,
                    answer_template TEXT NOT NULL,
                    dynamic_variables JSON NOT NULL,
                    usage_count INTEGER DEFAULT 0,
                    last_used_at TEXT,
                    created_at TEXT NOT NULL
                )
                """)

                # Vault History Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qa_id TEXT NOT NULL,
                    answer_template TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY(qa_id) REFERENCES vault(qa_id) ON DELETE CASCADE
                )
                """)

                # Jobs Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    fingerprint TEXT UNIQUE NOT NULL,
                    platform TEXT NOT NULL,
                    company TEXT NOT NULL,
                    title TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT NOT NULL,
                    description TEXT,
                    salary_range TEXT,
                    seniority_level TEXT,
                    posted_date TEXT,
                    match_score REAL DEFAULT 0.0,
                    priority_score REAL DEFAULT 0.0,
                    match_reasons JSON,
                    missing_skills JSON,
                    status TEXT NOT NULL,
                    applied_at TEXT,
                    application_id TEXT,
                    confirmation_screenshot_path TEXT,
                    notes TEXT
                )
                """)
                self._ensure_columns(conn, "jobs", {
                    "salary_range": "TEXT",
                    "seniority_level": "TEXT",
                    "match_reasons": "JSON",
                    "missing_skills": "JSON",
                    "application_id": "TEXT",
                    "confirmation_screenshot_path": "TEXT"
                })

                # HITL Events Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS hitl_events (
                    event_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    company TEXT NOT NULL,
                    role_title TEXT NOT NULL,
                    question_text TEXT NOT NULL,
                    input_type TEXT NOT NULL,
                    options JSON,
                    ai_suggested_draft TEXT,
                    user_answer TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """)
                self._ensure_columns(conn, "hitl_events", {
                    "resolved_at": "TEXT"
                })

                # Outreach Records Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS outreach_records (
                    outreach_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    recipient_name TEXT,
                    recipient_title TEXT,
                    recipient_contact TEXT,
                    message_content TEXT NOT NULL,
                    status TEXT NOT NULL,
                    sent_at TEXT,
                    created_at TEXT NOT NULL
                )
                """)

                # Emails Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    message_id TEXT PRIMARY KEY,
                    sender TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body_text TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    associated_job_id TEXT,
                    intent TEXT NOT NULL,
                    scheduling_links JSON,
                    has_tracking_pixels INTEGER DEFAULT 0,
                    processed INTEGER DEFAULT 0
                )
                """)

                # Job Checkpoints Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_checkpoints (
                    job_id TEXT PRIMARY KEY,
                    current_step INTEGER NOT NULL,
                    total_steps INTEGER NOT NULL,
                    filled_inputs JSON NOT NULL,
                    last_url TEXT,
                    screenshot_path TEXT,
                    updated_at TEXT NOT NULL
                )
                """)

                # Logs Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    level TEXT NOT NULL,
                    module TEXT NOT NULL,
                    job_id TEXT,
                    message TEXT NOT NULL,
                    metadata JSON
                )
                """)

                cursor.execute("""
                INSERT OR REPLACE INTO _schema_versions (version, applied_at, description)
                VALUES (1, datetime('now'), 'Initial comprehensive schema setup with WAL mode')
                """)
                conn.commit()

    # --- Profile Operations ---
    def save_profile(self, profile: CandidateProfile):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO profiles (id, data, updated_at)
                VALUES (?, ?, ?)
                """, (profile.id, json.dumps(profile.dict()), profile.updated_at))
                conn.commit()

    def get_profile(self, profile_id: str = "default_user") -> Optional[CandidateProfile]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT data FROM profiles WHERE id = ?", (profile_id,))
            row = cursor.fetchone()
            if row:
                return CandidateProfile(**json.loads(row["data"]))
            return None

    # --- Vault Operations ---
    def save_vault_entry(self, entry: VaultEntry):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Check if updating an existing entry to store history
                cursor.execute("SELECT answer_template FROM vault WHERE qa_id = ?", (entry.qa_id,))
                existing = cursor.fetchone()
                if existing and existing["answer_template"] != entry.answer_template:
                    cursor.execute("""
                    INSERT INTO vault_history (qa_id, answer_template, changed_at)
                    VALUES (?, ?, datetime('now'))
                    """, (entry.qa_id, existing["answer_template"]))

                cursor.execute("""
                INSERT OR REPLACE INTO vault 
                (qa_id, slot_type, slot_key, question_pattern, embedding, answer_template, dynamic_variables, usage_count, last_used_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.qa_id,
                    entry.slot_type.value,
                    entry.slot_key,
                    entry.question_pattern,
                    json.dumps(entry.embedding),
                    entry.answer_template,
                    json.dumps(entry.dynamic_variables),
                    entry.usage_count,
                    entry.last_used_at,
                    entry.created_at
                ))
                conn.commit()

    def get_all_vault_entries(self) -> List[VaultEntry]:
        entries = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vault ORDER BY usage_count DESC")
            for row in cursor.fetchall():
                entries.append(VaultEntry(
                    qa_id=row["qa_id"],
                    slot_type=row["slot_type"],
                    slot_key=row["slot_key"],
                    question_pattern=row["question_pattern"],
                    embedding=json.loads(row["embedding"]),
                    answer_template=row["answer_template"],
                    dynamic_variables=json.loads(row["dynamic_variables"]),
                    usage_count=row["usage_count"],
                    last_used_at=row["last_used_at"],
                    created_at=row["created_at"]
                ))
        return entries

    def increment_vault_usage(self, qa_id: str):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE vault 
                SET usage_count = usage_count + 1, last_used_at = datetime('now')
                WHERE qa_id = ?
                """, (qa_id,))
                conn.commit()

    # --- Job Operations ---
    def save_job(self, job: JobListing) -> bool:
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("""
                    INSERT OR REPLACE INTO jobs 
                    (job_id, fingerprint, platform, company, title, location, url, description, 
                     salary_range, seniority_level, posted_date, match_score, priority_score, 
                     match_reasons, missing_skills, status, applied_at, application_id, 
                     confirmation_screenshot_path, notes)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        job.job_id, job.fingerprint, job.platform, job.company, job.title,
                        job.location, job.url, job.description, job.salary_range,
                        job.seniority_level, job.posted_date, job.match_score, job.priority_score,
                        json.dumps(job.match_reasons), json.dumps(job.missing_skills),
                        job.status.value, job.applied_at, job.application_id,
                        job.confirmation_screenshot_path, job.notes
                    ))
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False

    def get_jobs(self, status: Optional[str] = None) -> List[JobListing]:
        jobs = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if status:
                cursor.execute("SELECT * FROM jobs WHERE status = ? ORDER BY priority_score DESC", (status,))
            else:
                cursor.execute("SELECT * FROM jobs ORDER BY priority_score DESC")
            for row in cursor.fetchall():
                jobs.append(JobListing(
                    job_id=row["job_id"],
                    fingerprint=row["fingerprint"],
                    platform=row["platform"],
                    company=row["company"],
                    title=row["title"],
                    location=row["location"],
                    url=row["url"],
                    description=row["description"] or "",
                    salary_range=row["salary_range"],
                    seniority_level=row["seniority_level"],
                    posted_date=row["posted_date"],
                    match_score=row["match_score"],
                    priority_score=row["priority_score"],
                    match_reasons=json.loads(row["match_reasons"]) if row["match_reasons"] else [],
                    missing_skills=json.loads(row["missing_skills"]) if row["missing_skills"] else [],
                    status=ApplicationStatus(row["status"]),
                    applied_at=row["applied_at"],
                    application_id=row["application_id"],
                    confirmation_screenshot_path=row["confirmation_screenshot_path"],
                    notes=row["notes"]
                ))
        return jobs

    def update_job_status(self, job_id: str, status: ApplicationStatus, notes: Optional[str] = None, application_id: Optional[str] = None):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE jobs 
                SET status = ?, notes = COALESCE(?, notes), application_id = COALESCE(?, application_id),
                    applied_at = CASE WHEN ? = 'SUBMITTED' THEN datetime('now') ELSE applied_at END
                WHERE job_id = ?
                """, (status.value, notes, application_id, status.value, job_id))
                conn.commit()

    # --- HITL Event Operations ---
    def save_hitl_event(self, event: HITLEvent):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO hitl_events
                (event_id, job_id, company, role_title, question_text, input_type, options, ai_suggested_draft, user_answer, status, created_at, resolved_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id, event.job_id, event.company, event.role_title,
                    event.question_text, event.input_type, json.dumps(event.options),
                    event.ai_suggested_draft, event.user_answer, event.status,
                    event.created_at, event.resolved_at
                ))
                conn.commit()

    def resolve_hitl_event(self, event_id: str, user_answer: str) -> bool:
        """Atomically resolves a pending HITL event to prevent race conditions."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE hitl_events 
                SET status = 'RESOLVED', user_answer = ?, resolved_at = datetime('now')
                WHERE event_id = ? AND status = 'PENDING'
                """, (user_answer, event_id))
                conn.commit()
                return cursor.rowcount > 0

    def get_pending_hitl_events(self) -> List[HITLEvent]:
        events = []
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE status = 'PENDING' ORDER BY created_at ASC")
            for row in cursor.fetchall():
                events.append(HITLEvent(
                    event_id=row["event_id"],
                    job_id=row["job_id"],
                    company=row["company"],
                    role_title=row["role_title"],
                    question_text=row["question_text"],
                    input_type=row["input_type"],
                    options=json.loads(row["options"]) if row["options"] else [],
                    ai_suggested_draft=row["ai_suggested_draft"] or "",
                    user_answer=row["user_answer"],
                    status=row["status"],
                    created_at=row["created_at"],
                    resolved_at=row["resolved_at"]
                ))
        return events

    # --- Outreach Record Operations ---
    def save_outreach_record(self, record: OutreachRecord):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO outreach_records
                (outreach_id, job_id, channel, recipient_name, recipient_title, recipient_contact, message_content, status, sent_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.outreach_id, record.job_id, record.channel.value,
                    record.recipient_name, record.recipient_title, record.recipient_contact,
                    record.message_content, record.status, record.sent_at, record.created_at
                ))
                conn.commit()

    # --- Email Message Operations ---
    def save_email(self, email: EmailMessage):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO emails
                (message_id, sender, recipient, subject, body_text, received_at, associated_job_id, intent, scheduling_links, has_tracking_pixels, processed)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email.message_id, email.sender, email.recipient, email.subject,
                    email.body_text, email.received_at, email.associated_job_id,
                    email.intent.value, json.dumps(email.scheduling_links),
                    1 if email.has_tracking_pixels else 0, 1 if email.processed else 0
                ))
                conn.commit()

    # --- Job Checkpoint Operations ---
    def save_checkpoint(self, checkpoint: JobCheckpoint):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO job_checkpoints
                (job_id, current_step, total_steps, filled_inputs, last_url, screenshot_path, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    checkpoint.job_id, checkpoint.current_step, checkpoint.total_steps,
                    json.dumps(checkpoint.filled_inputs), checkpoint.last_url,
                    checkpoint.screenshot_path, checkpoint.updated_at
                ))
                conn.commit()

    def get_checkpoint(self, job_id: str) -> Optional[JobCheckpoint]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_checkpoints WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if row:
                return JobCheckpoint(
                    job_id=row["job_id"],
                    current_step=row["current_step"],
                    total_steps=row["total_steps"],
                    filled_inputs=json.loads(row["filled_inputs"]),
                    last_url=row["last_url"],
                    screenshot_path=row["screenshot_path"],
                    updated_at=row["updated_at"]
                )
            return None

    # --- Logging Operations ---
    def log(self, level: str, module: str, message: str, job_id: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO logs (timestamp, level, module, job_id, message, metadata)
                VALUES (datetime('now'), ?, ?, ?, ?, ?)
                """, (level, module, job_id, message, json.dumps(metadata) if metadata else None))
                conn.commit()


db = DatabaseManager()
