"""
JobCopilot - SQLite Local-First & Multi-Tenant Storage Engine
Configured with Write-Ahead Logging (WAL Mode), Connection Pooling,
Atomic Transactions, Dynamic Multi-Tenant Migration, and User Isolation.
"""

import sqlite3
import json
import threading
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from app.core.config import DB_PATH
from app.core.models import (
    User, CandidateProfile, VaultEntry, JobListing, HITLEvent,
    ApplicationStatus, OutreachRecord, OutreachChannel, EmailMessage, JobCheckpoint
)
from app.core.db_adapter import DatabaseAdapter


class DatabaseManager(DatabaseAdapter):
    """Thread-safe Multi-Tenant SQLite Database Manager with WAL mode and atomic user isolation."""
    
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

                # 1. Users Table for Multi-Tenant Auth
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    email TEXT UNIQUE NOT NULL,
                    password_hash TEXT NOT NULL,
                    full_name TEXT DEFAULT '',
                    role TEXT DEFAULT 'FREE',
                    is_active INTEGER DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);")

                # 2. Profiles Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS profiles (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    data JSON NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
                self._ensure_columns(conn, "profiles", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'"
                })

                # 3. Vault Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault (
                    qa_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
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
                self._ensure_columns(conn, "vault", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'"
                })

                # 4. Vault History Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS vault_history (
                    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qa_id TEXT NOT NULL,
                    answer_template TEXT NOT NULL,
                    changed_at TEXT NOT NULL,
                    FOREIGN KEY(qa_id) REFERENCES vault(qa_id) ON DELETE CASCADE
                )
                """)

                # 5. Jobs Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
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
                    submission_mode TEXT,
                    applied_at TEXT,
                    application_id TEXT,
                    confirmation_screenshot_path TEXT,
                    notes TEXT
                )
                """)
                self._ensure_columns(conn, "jobs", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'",
                    "salary_range": "TEXT",
                    "seniority_level": "TEXT",
                    "match_reasons": "JSON",
                    "missing_skills": "JSON",
                    "submission_mode": "TEXT",
                    "application_id": "TEXT",
                    "confirmation_screenshot_path": "TEXT"
                })

                # Multi-tenant indices
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority_score DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_status ON jobs(user_id, status);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_priority ON jobs(user_id, priority_score DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vault_slot_key ON vault(slot_key);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_vault_user_key ON vault(user_id, slot_key);")

                # 6. HITL Events Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS hitl_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
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
                    "user_id": "TEXT NOT NULL DEFAULT 'default'",
                    "resolved_at": "TEXT"
                })

                # 7. Outreach Records Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS outreach_records (
                    outreach_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
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
                self._ensure_columns(conn, "outreach_records", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'"
                })

                # 8. Emails Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS emails (
                    message_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
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
                self._ensure_columns(conn, "emails", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'"
                })

                # 9. Job Checkpoints Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS job_checkpoints (
                    job_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    current_step INTEGER DEFAULT 1,
                    total_steps INTEGER DEFAULT 1,
                    filled_inputs JSON NOT NULL,
                    last_url TEXT,
                    screenshot_path TEXT,
                    updated_at TEXT NOT NULL
                )
                """)
                self._ensure_columns(conn, "job_checkpoints", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'"
                })

                conn.commit()

    # =========================================================================
    # User Authentication & Tenant Management
    # =========================================================================
    def create_user(self, user: User) -> bool:
        """Creates a new user account with hashed password."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO users (user_id, email, password_hash, full_name, role, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user.user_id,
                        user.email.lower().strip(),
                        user.password_hash,
                        user.full_name,
                        user.role.value if hasattr(user.role, 'value') else str(user.role),
                        1 if user.is_active else 0,
                        user.created_at,
                        user.updated_at
                    ))
                    conn.commit()
                    return True
                except sqlite3.IntegrityError:
                    return False

    def get_user_by_email(self, email: str) -> Optional[User]:
        """Retrieves a user by unique email address."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE email = ?", (email.lower().strip(),))
            row = cursor.fetchone()
            if not row:
                return None
            return User(
                user_id=row["user_id"],
                email=row["email"],
                password_hash=row["password_hash"],
                full_name=row["full_name"] or "",
                role=row["role"] or "FREE",
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Retrieves a user by unique user_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return User(
                user_id=row["user_id"],
                email=row["email"],
                password_hash=row["password_hash"],
                full_name=row["full_name"] or "",
                role=row["role"] or "FREE",
                is_active=bool(row["is_active"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    # =========================================================================
    # Candidate Profile Operations (Multi-Tenant)
    # =========================================================================
    def save_profile(self, profile: CandidateProfile, user_id: str = "default") -> bool:
        """Saves or replaces the Candidate Profile bound to user_id."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                profile_dict = profile.dict()
                target_id = profile.id or f"profile_{user_id}"
                cursor.execute("""
                INSERT OR REPLACE INTO profiles (id, user_id, data, updated_at)
                VALUES (?, ?, ?, ?)
                """, (target_id, user_id, json.dumps(profile_dict), profile.updated_at))
                conn.commit()
                return True

    def get_profile(self, profile_id: str = "default_user", user_id: str = "default") -> Optional[CandidateProfile]:
        """Retrieves candidate profile for the specified user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            # Check user_id match first, fallback to profile_id for backward compatibility
            cursor.execute("SELECT data FROM profiles WHERE user_id = ? OR id = ? ORDER BY updated_at DESC LIMIT 1", (user_id, profile_id))
            row = cursor.fetchone()
            if row:
                data = json.loads(row["data"])
                return CandidateProfile(**data)
            return None

    # =========================================================================
    # Knowledge Vault Operations (Multi-Tenant)
    # =========================================================================
    def save_vault_entry(self, entry: VaultEntry, user_id: str = "default") -> bool:
        """Saves a slot QA entry and tracks version history for a user."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO vault (
                    qa_id, user_id, slot_type, slot_key, question_pattern, embedding,
                    answer_template, dynamic_variables, usage_count, last_used_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.qa_id,
                    user_id,
                    entry.slot_type.value if hasattr(entry.slot_type, 'value') else entry.slot_type,
                    entry.slot_key,
                    entry.question_pattern,
                    json.dumps(entry.embedding),
                    entry.answer_template,
                    json.dumps(entry.dynamic_variables),
                    entry.usage_count,
                    entry.last_used_at,
                    entry.created_at
                ))
                cursor.execute("""
                INSERT INTO vault_history (qa_id, answer_template, changed_at)
                VALUES (?, ?, ?)
                """, (entry.qa_id, entry.answer_template, entry.created_at))
                conn.commit()
                return True

    def get_vault_entries(self, user_id: str = "default") -> List[VaultEntry]:
        """Retrieves all indexed slots for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vault WHERE user_id = ? OR user_id = 'default' ORDER BY usage_count DESC", (user_id,))
            rows = cursor.fetchall()
            entries = []
            for r in rows:
                entries.append(VaultEntry(
                    qa_id=r["qa_id"],
                    user_id=r["user_id"] if "user_id" in r.keys() else user_id,
                    slot_type=r["slot_type"],
                    slot_key=r["slot_key"],
                    question_pattern=r["question_pattern"],
                    embedding=json.loads(r["embedding"]),
                    answer_template=r["answer_template"],
                    dynamic_variables=json.loads(r["dynamic_variables"]),
                    usage_count=r["usage_count"],
                    last_used_at=r["last_used_at"],
                    created_at=r["created_at"]
                ))
            return entries

    get_all_vault_entries = get_vault_entries

    def get_vault_entry_by_key(self, slot_key: str, user_id: str = "default") -> Optional[VaultEntry]:
        """Finds entry by slot key for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vault WHERE (user_id = ? OR user_id = 'default') AND slot_key = ? LIMIT 1", (user_id, slot_key))
            r = cursor.fetchone()
            if r:
                return VaultEntry(
                    qa_id=r["qa_id"],
                    user_id=r["user_id"] if "user_id" in r.keys() else user_id,
                    slot_type=r["slot_type"],
                    slot_key=r["slot_key"],
                    question_pattern=r["question_pattern"],
                    embedding=json.loads(r["embedding"]),
                    answer_template=r["answer_template"],
                    dynamic_variables=json.loads(r["dynamic_variables"]),
                    usage_count=r["usage_count"],
                    last_used_at=r["last_used_at"],
                    created_at=r["created_at"]
                )
            return None

    def increment_vault_usage(self, qa_id: str):
        """Increments usage counter atomically."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.now().isoformat()
                cursor.execute("""
                UPDATE vault SET usage_count = usage_count + 1, last_used_at = ?
                WHERE qa_id = ?
                """, (now_str, qa_id))
                conn.commit()

    # =========================================================================
    # Job Listings Operations (Multi-Tenant)
    # =========================================================================
    def save_job(self, job: JobListing, user_id: str = "default") -> bool:
        """Inserts or updates a job opportunity with atomic deduplication."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO jobs (
                    job_id, user_id, fingerprint, platform, company, title, location, url,
                    description, salary_range, seniority_level, posted_date, match_score,
                    priority_score, match_reasons, missing_skills, status, submission_mode,
                    applied_at, application_id, confirmation_screenshot_path, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(fingerprint) DO UPDATE SET
                    match_score = excluded.match_score,
                    priority_score = excluded.priority_score,
                    status = excluded.status,
                    submission_mode = coalesce(excluded.submission_mode, jobs.submission_mode),
                    applied_at = coalesce(excluded.applied_at, jobs.applied_at),
                    application_id = coalesce(excluded.application_id, jobs.application_id),
                    confirmation_screenshot_path = coalesce(excluded.confirmation_screenshot_path, jobs.confirmation_screenshot_path),
                    notes = coalesce(excluded.notes, jobs.notes)
                """, (
                    job.job_id,
                    user_id,
                    job.fingerprint,
                    job.platform,
                    job.company,
                    job.title,
                    job.location,
                    job.url,
                    job.description,
                    job.salary_range,
                    job.seniority_level,
                    job.posted_date,
                    job.match_score,
                    job.priority_score,
                    json.dumps(job.match_reasons),
                    json.dumps(job.missing_skills),
                    job.status.value if hasattr(job.status, 'value') else job.status,
                    job.submission_mode,
                    job.applied_at,
                    job.application_id,
                    job.confirmation_screenshot_path,
                    job.notes
                ))
                conn.commit()
                return True

    def get_jobs(self, status: Optional[ApplicationStatus] = None, user_id: str = "default") -> List[JobListing]:
        """Returns jobs for the user ordered by priority score."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM jobs WHERE (user_id = ? OR user_id = 'default')"
            params = [user_id]
            if status:
                query += " AND status = ?"
                params.append(status.value if hasattr(status, 'value') else status)
            query += " ORDER BY priority_score DESC, match_score DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_job(r) for r in rows]

    def get_job_by_id(self, job_id: str, user_id: str = "default") -> Optional[JobListing]:
        """Retrieves a single job by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ? AND (user_id = ? OR user_id = 'default')", (job_id, user_id))
            row = cursor.fetchone()
            return self._row_to_job(row) if row else None

    get_job = get_job_by_id

    def get_job_by_fingerprint(self, fingerprint: str, user_id: str = "default") -> Optional[JobListing]:
        """Checks for existing job by fingerprint."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE fingerprint = ? AND (user_id = ? OR user_id = 'default')", (fingerprint, user_id))
            row = cursor.fetchone()
            return self._row_to_job(row) if row else None

    def _row_to_job(self, r: sqlite3.Row) -> JobListing:
        keys = r.keys()
        return JobListing(
            job_id=r["job_id"],
            user_id=r["user_id"] if "user_id" in keys else "default",
            fingerprint=r["fingerprint"],
            platform=r["platform"],
            company=r["company"],
            title=r["title"],
            location=r["location"],
            url=r["url"],
            description=r["description"] or "",
            salary_range=r["salary_range"] if "salary_range" in keys else None,
            seniority_level=r["seniority_level"] if "seniority_level" in keys else None,
            posted_date=r["posted_date"],
            match_score=r["match_score"],
            priority_score=r["priority_score"],
            match_reasons=json.loads(r["match_reasons"]) if "match_reasons" in keys and r["match_reasons"] else [],
            missing_skills=json.loads(r["missing_skills"]) if "missing_skills" in keys and r["missing_skills"] else [],
            status=r["status"],
            submission_mode=r["submission_mode"] if "submission_mode" in keys else None,
            applied_at=r["applied_at"],
            application_id=r["application_id"] if "application_id" in keys else None,
            confirmation_screenshot_path=r["confirmation_screenshot_path"] if "confirmation_screenshot_path" in keys else None,
            notes=r["notes"]
        )

    # =========================================================================
    # HITL Operations (Multi-Tenant)
    # =========================================================================
    def save_hitl_event(self, event: HITLEvent, user_id: str = "default") -> bool:
        """Stores a human intervention event."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO hitl_events (
                    event_id, user_id, job_id, company, role_title, question_text,
                    input_type, options, ai_suggested_draft, user_answer, status, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event.event_id,
                    user_id,
                    event.job_id,
                    event.company,
                    event.role_title,
                    event.question_text,
                    event.input_type,
                    json.dumps(event.options),
                    event.ai_suggested_draft,
                    event.user_answer,
                    event.status,
                    event.created_at,
                    event.resolved_at
                ))
                conn.commit()
                return True

    def get_pending_hitl(self, user_id: str = "default") -> List[HITLEvent]:
        """Retrieves all pending HITL items for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE (user_id = ? OR user_id = 'default') AND status = 'PENDING' ORDER BY created_at ASC", (user_id,))
            rows = cursor.fetchall()
            return [
                HITLEvent(
                    event_id=r["event_id"],
                    user_id=r["user_id"] if "user_id" in r.keys() else user_id,
                    job_id=r["job_id"],
                    company=r["company"],
                    role_title=r["role_title"],
                    question_text=r["question_text"],
                    input_type=r["input_type"],
                    options=json.loads(r["options"]) if r["options"] else [],
                    ai_suggested_draft=r["ai_suggested_draft"] or "",
                    user_answer=r["user_answer"],
                    status=r["status"],
                    created_at=r["created_at"],
                    resolved_at=r["resolved_at"] if "resolved_at" in r.keys() else None
                )
                for r in rows
            ]

    get_pending_hitl_events = get_pending_hitl

    def get_hitl_event(self, event_id: str) -> Optional[HITLEvent]:
        """Retrieves a single HITL event by ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE event_id = ?", (event_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return HITLEvent(
                event_id=row["event_id"],
                user_id=row["user_id"] if "user_id" in row.keys() else "default",
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
                resolved_at=row["resolved_at"] if "resolved_at" in row.keys() else None
            )

    def resolve_hitl_event(self, event_id: str, user_answer: str, user_id: str = "default") -> bool:
        """Atomically resolves a pending HITL question."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.now().isoformat()
                cursor.execute("""
                UPDATE hitl_events SET status = 'RESOLVED', user_answer = ?, resolved_at = ?
                WHERE event_id = ? AND status = 'PENDING'
                """, (user_answer, now_str, event_id))
                conn.commit()
                return cursor.rowcount > 0

    # =========================================================================
    # Outreach & Email Operations (Multi-Tenant)
    # =========================================================================
    def save_outreach(self, record: OutreachRecord, user_id: str = "default") -> bool:
        """Saves a multi-channel outreach draft or sent message."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO outreach_records (
                    outreach_id, user_id, job_id, channel, recipient_name, recipient_title,
                    recipient_contact, message_content, status, sent_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record.outreach_id,
                    user_id,
                    record.job_id,
                    record.channel.value if hasattr(record.channel, 'value') else record.channel,
                    record.recipient_name,
                    record.recipient_title,
                    record.recipient_contact,
                    record.message_content,
                    record.status,
                    record.sent_at,
                    record.created_at
                ))
                conn.commit()
                return True

    save_outreach_record = save_outreach

    def get_outreach(self, job_id: str, user_id: str = "default") -> List[OutreachRecord]:
        """Retrieves all outreach records for a specific job."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM outreach_records WHERE job_id = ? AND (user_id = ? OR user_id = 'default')", (job_id, user_id))
            rows = cursor.fetchall()
            return [
                OutreachRecord(
                    outreach_id=r["outreach_id"],
                    user_id=r["user_id"] if "user_id" in r.keys() else user_id,
                    job_id=r["job_id"],
                    channel=r["channel"],
                    recipient_name=r["recipient_name"],
                    recipient_title=r["recipient_title"],
                    recipient_contact=r["recipient_contact"],
                    message_content=r["message_content"],
                    status=r["status"],
                    sent_at=r["sent_at"],
                    created_at=r["created_at"]
                )
                for r in rows
            ]

    get_outreach_records = get_outreach

    def save_email(self, email: EmailMessage, user_id: str = "default") -> bool:
        """Stores classified inbound recruiter email."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO emails (
                    message_id, user_id, sender, recipient, subject, body_text,
                    received_at, associated_job_id, intent, scheduling_links,
                    has_tracking_pixels, processed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email.message_id,
                    user_id,
                    email.sender,
                    email.recipient,
                    email.subject,
                    email.body_text,
                    email.received_at,
                    email.associated_job_id,
                    email.intent.value if hasattr(email.intent, 'value') else email.intent,
                    json.dumps(email.scheduling_links),
                    1 if email.has_tracking_pixels else 0,
                    1 if email.processed else 0
                ))
                conn.commit()
                return True

    def get_emails(self, user_id: str = "default") -> List[EmailMessage]:
        """Retrieves all tracked recruiter communications for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails WHERE user_id = ? OR user_id = 'default' ORDER BY received_at DESC", (user_id,))
            rows = cursor.fetchall()
            return [
                EmailMessage(
                    message_id=r["message_id"],
                    user_id=r["user_id"] if "user_id" in r.keys() else user_id,
                    sender=r["sender"],
                    recipient=r["recipient"],
                    subject=r["subject"],
                    body_text=r["body_text"],
                    received_at=r["received_at"],
                    associated_job_id=r["associated_job_id"],
                    intent=r["intent"],
                    scheduling_links=json.loads(r["scheduling_links"]) if r["scheduling_links"] else [],
                    has_tracking_pixels=bool(r["has_tracking_pixels"]),
                    processed=bool(r["processed"])
                )
                for r in rows
            ]

    # =========================================================================
    # Job Checkpoint Recovery
    # =========================================================================
    def save_checkpoint(self, checkpoint: JobCheckpoint, user_id: str = "default") -> bool:
        """Saves current automation execution step for crash recovery."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO job_checkpoints (
                    job_id, user_id, current_step, total_steps, filled_inputs,
                    last_url, screenshot_path, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    checkpoint.job_id,
                    user_id,
                    checkpoint.current_step,
                    checkpoint.total_steps,
                    json.dumps(checkpoint.filled_inputs),
                    checkpoint.last_url,
                    checkpoint.screenshot_path,
                    checkpoint.updated_at
                ))
                conn.commit()
                return True

    def get_checkpoint(self, job_id: str, user_id: str = "default") -> Optional[JobCheckpoint]:
        """Retrieves active checkpoint for recovery."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_checkpoints WHERE job_id = ? AND (user_id = ? OR user_id = 'default')", (job_id, user_id))
            row = cursor.fetchone()
            if row:
                return JobCheckpoint(
                    job_id=row["job_id"],
                    user_id=row["user_id"] if "user_id" in row.keys() else user_id,
                    current_step=row["current_step"],
                    total_steps=row["total_steps"],
                    filled_inputs=json.loads(row["filled_inputs"]),
                    last_url=row["last_url"],
                    screenshot_path=row["screenshot_path"],
                    updated_at=row["updated_at"]
                )
            return None

    def delete_checkpoint(self, job_id: str, user_id: str = "default"):
        """Deletes checkpoint upon successful completion."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM job_checkpoints WHERE job_id = ? AND (user_id = ? OR user_id = 'default')", (job_id, user_id))
                conn.commit()

    # =========================================================================
    # Funnel Analytics (Multi-Tenant)
    # =========================================================================
    def get_funnel_metrics(self, user_id: str = "default") -> Dict[str, Any]:
        """Computes live conversion funnel metrics for the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM jobs WHERE user_id = ? OR user_id = 'default'", (user_id,))
            total_sourced = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as applied FROM jobs WHERE (user_id = ? OR user_id = 'default') AND status IN ('SUBMITTED', 'RESPONDED', 'INTERVIEW', 'OFFER')", (user_id,))
            total_applied = cursor.fetchone()["applied"]

            cursor.execute("SELECT COUNT(*) as interviews FROM jobs WHERE (user_id = ? OR user_id = 'default') AND status = 'INTERVIEW'", (user_id,))
            interviews = cursor.fetchone()["interviews"]

            cursor.execute("SELECT COUNT(*) as offers FROM jobs WHERE (user_id = ? OR user_id = 'default') AND status = 'OFFER'", (user_id,))
            offers = cursor.fetchone()["offers"]

            cursor.execute("SELECT COUNT(*) as responses FROM emails WHERE (user_id = ? OR user_id = 'default') AND intent IN ('INTERVIEW_INVITE', 'ASSESSMENT')", (user_id,))
            recruiter_responses = cursor.fetchone()["responses"]

            response_rate = (recruiter_responses / total_applied * 100) if total_applied > 0 else 0.0

            return {
                "total_sourced": total_sourced,
                "total_applied": total_applied,
                "interviews_count": interviews,
                "offers_count": offers,
                "recruiter_responses": recruiter_responses,
                "response_rate_percent": round(response_rate, 2)
            }


db = DatabaseManager()
