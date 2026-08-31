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
from app.core.credential_vault import cred_vault


class DatabaseManager(DatabaseAdapter):
    """Thread-safe Multi-Tenant SQLite Database Manager with WAL mode and atomic user isolation."""
    
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._init_pragmas()
        self._run_migrations()

    def get_connection(self) -> sqlite3.Connection:
        """Returns a high-performance thread-safe SQLite connection with WAL pragmas."""
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA mmap_size = 268435456;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    def _init_pragmas(self):
        with sqlite3.connect(str(self.db_path), timeout=10.0) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 5000;")
            conn.execute("PRAGMA cache_size = -64000;")
            conn.execute("PRAGMA mmap_size = 268435456;")
            conn.execute("PRAGMA temp_store = MEMORY;")
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

                # 10. Token Revocation Blacklist Table (F-08)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS revoked_tokens (
                    jti TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    revoked_at TEXT NOT NULL,
                    expires_at TEXT
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_revoked_tokens_jti ON revoked_tokens(jti);")

                # 11. User Daily Rate Limiting Usage Table (F-13)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_daily_usage (
                    user_id TEXT NOT NULL,
                    date TEXT NOT NULL,
                    apply_count INTEGER DEFAULT 0,
                    PRIMARY KEY (user_id, date)
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_daily_usage_user_date ON user_daily_usage(user_id, date);")

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

    def update_user_role(self, user_id: str, role: str) -> bool:
        """Updates user subscription tier."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET role = ?, updated_at = ? WHERE user_id = ?",
                    (role, datetime.now().isoformat(), user_id)
                )
                conn.commit()
                return cursor.rowcount > 0

    def update_user_password(self, user_id: str, new_password_hash: str) -> bool:
        """Updates user password hash (e.g. during Argon2id migration)."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET password_hash = ?, updated_at = ? WHERE user_id = ?",
                    (new_password_hash, datetime.now().isoformat(), user_id)
                )
                conn.commit()
                return cursor.rowcount > 0

    def revoke_token(self, jti: str, user_id: str, expires_at: Optional[str] = None) -> bool:
        """Adds a token's jti to the revoked_tokens blacklist."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.now().isoformat()
                cursor.execute("""
                INSERT OR REPLACE INTO revoked_tokens (jti, user_id, revoked_at, expires_at)
                VALUES (?, ?, ?, ?)
                """, (jti, user_id, now_str, expires_at or ""))
                conn.commit()
                return True

    def is_token_revoked(self, jti: str) -> bool:
        """Checks whether a token's jti is in the revoked blacklist."""
        if not jti:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM revoked_tokens WHERE jti = ? LIMIT 1", (jti,))
            return cursor.fetchone() is not None

    def get_daily_usage(self, user_id: str, date_str: str) -> int:
        """Gets count of daily applications for a user on a given date (YYYY-MM-DD)."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT apply_count FROM user_daily_usage WHERE user_id = ? AND date = ?", (user_id, date_str))
            row = cursor.fetchone()
            return int(row["apply_count"]) if row else 0

    def increment_daily_usage(self, user_id: str, date_str: str) -> int:
        """Increments daily application count atomically and returns new total."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO user_daily_usage (user_id, date, apply_count)
                VALUES (?, ?, 1)
                ON CONFLICT(user_id, date) DO UPDATE SET apply_count = apply_count + 1
                """, (user_id, date_str))
                conn.commit()
                cursor.execute("SELECT apply_count FROM user_daily_usage WHERE user_id = ? AND date = ?", (user_id, date_str))
                row = cursor.fetchone()
                return int(row["apply_count"]) if row else 1

    # =========================================================================
    # Candidate Profile Operations (Multi-Tenant with PII Encryption at Rest)
    # =========================================================================
    @staticmethod
    def _encrypt_profile_dict(p_dict: Dict[str, Any]) -> Dict[str, Any]:
        encrypted = dict(p_dict)
        if encrypted.get("phone"):
            encrypted["phone"] = cred_vault.encrypt_field(encrypted["phone"])
        if encrypted.get("location"):
            encrypted["location"] = cred_vault.encrypt_field(encrypted["location"])
        if "preferences" in encrypted and isinstance(encrypted["preferences"], dict):
            prefs = dict(encrypted["preferences"])
            if prefs.get("expected_ctc"):
                prefs["expected_ctc"] = cred_vault.encrypt_field(prefs["expected_ctc"])
            if prefs.get("current_employer"):
                prefs["current_employer"] = cred_vault.encrypt_field(prefs["current_employer"])
            if prefs.get("why_looking_for_role"):
                prefs["why_looking_for_role"] = cred_vault.encrypt_field(prefs["why_looking_for_role"])
            encrypted["preferences"] = prefs
        encrypted["_pii_encrypted"] = True
        return encrypted

    @staticmethod
    def _decrypt_profile_dict(p_dict: Dict[str, Any]) -> Dict[str, Any]:
        if not p_dict.get("_pii_encrypted"):
            return p_dict
        decrypted = dict(p_dict)
        if decrypted.get("phone"):
            decrypted["phone"] = cred_vault.decrypt_field(decrypted["phone"])
        if decrypted.get("location"):
            decrypted["location"] = cred_vault.decrypt_field(decrypted["location"])
        if "preferences" in decrypted and isinstance(decrypted["preferences"], dict):
            prefs = dict(decrypted["preferences"])
            if prefs.get("expected_ctc"):
                prefs["expected_ctc"] = cred_vault.decrypt_field(prefs["expected_ctc"])
            if prefs.get("current_employer"):
                prefs["current_employer"] = cred_vault.decrypt_field(prefs["current_employer"])
            if prefs.get("why_looking_for_role"):
                prefs["why_looking_for_role"] = cred_vault.decrypt_field(prefs["why_looking_for_role"])
            decrypted["preferences"] = prefs
        decrypted.pop("_pii_encrypted", None)
        return decrypted

    def save_profile(self, profile: CandidateProfile, user_id: str) -> bool:
        """Saves Candidate Profile with transparent AES-256-GCM PII encryption at rest."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                profile.user_id = user_id
                target_id = profile.id or user_id
                profile.id = target_id
                profile_dict = profile.dict()
                enc_dict = self._encrypt_profile_dict(profile_dict)
                cursor.execute("""
                INSERT OR REPLACE INTO profiles (id, user_id, data, updated_at)
                VALUES (?, ?, ?, ?)
                """, (target_id, user_id, json.dumps(enc_dict), profile.updated_at))
                conn.commit()
                return True

    def get_profile(self, user_id: str, profile_id: Optional[str] = None) -> Optional[CandidateProfile]:
        """Retrieves candidate profile strictly for user and transparently decrypts PII."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if profile_id:
                cursor.execute("SELECT data FROM profiles WHERE user_id = ? AND id = ? ORDER BY updated_at DESC LIMIT 1", (user_id, profile_id))
            else:
                cursor.execute("SELECT data FROM profiles WHERE user_id = ? ORDER BY updated_at DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if row:
                raw_dict = json.loads(row["data"])
                dec_dict = self._decrypt_profile_dict(raw_dict)
                return CandidateProfile(**dec_dict)
            return None

    def migrate_plaintext_profiles(self) -> int:
        """One-shot backfill helper to encrypt any legacy plaintext profile rows."""
        migrated = 0
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id, user_id, data, updated_at FROM profiles")
                rows = cursor.fetchall()
                for r in rows:
                    try:
                        data = json.loads(r["data"])
                        if not data.get("_pii_encrypted"):
                            enc = self._encrypt_profile_dict(data)
                            cursor.execute(
                                "UPDATE profiles SET data = ? WHERE id = ? AND user_id = ?",
                                (json.dumps(enc), r["id"], r["user_id"])
                            )
                            migrated += 1
                    except Exception:
                        pass
                conn.commit()
        return migrated

    # =========================================================================
    # Knowledge Vault Operations (Multi-Tenant)
    # =========================================================================
    def save_vault_entry(self, entry: VaultEntry, user_id: str) -> bool:
        """Saves a slot QA entry and tracks version history strictly for a user."""
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

    def get_vault_entries(self, user_id: str) -> List[VaultEntry]:
        """Retrieves all indexed slots strictly for the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vault WHERE user_id = ? ORDER BY usage_count DESC", (user_id,))
            rows = cursor.fetchall()
            entries = []
            for r in rows:
                entries.append(VaultEntry(
                    qa_id=r["qa_id"],
                    user_id=user_id,
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

    def get_vault_entry_by_key(self, slot_key: str, user_id: str) -> Optional[VaultEntry]:
        """Finds entry by slot key strictly for the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM vault WHERE user_id = ? AND slot_key = ? LIMIT 1", (user_id, slot_key))
            r = cursor.fetchone()
            if r:
                return VaultEntry(
                    qa_id=r["qa_id"],
                    user_id=user_id,
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
    def save_job(self, job: JobListing, user_id: str) -> bool:
        """Inserts or updates a job opportunity strictly for the user with atomic deduplication."""
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

    def get_jobs(self, user_id: str, status: Optional[ApplicationStatus] = None) -> List[JobListing]:
        """Returns jobs strictly for the specified user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM jobs WHERE user_id = ?"
            params = [user_id]
            if status:
                st_val = status.value if hasattr(status, 'value') else status
                query += " AND status = ?"
                params.append(st_val)
            query += " ORDER BY priority_score DESC, match_score DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_job(r) for r in rows]

    def get_job_by_id(self, job_id: str, user_id: str) -> Optional[JobListing]:
        """Retrieves a single job by ID strictly for the specified user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ? AND user_id = ? LIMIT 1", (job_id, user_id))
            row = cursor.fetchone()
            return self._row_to_job(row) if row else None

    get_job = get_job_by_id

    def get_job_by_fingerprint(self, fingerprint: str, user_id: str) -> Optional[JobListing]:
        """Checks for existing job by fingerprint strictly for the specified user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE fingerprint = ? AND user_id = ? LIMIT 1", (fingerprint, user_id))
            row = cursor.fetchone()
            return self._row_to_job(row) if row else None

    def _row_to_job(self, r: sqlite3.Row) -> JobListing:
        keys = r.keys()
        return JobListing(
            job_id=r["job_id"],
            user_id=r["user_id"] if "user_id" in keys else "",
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
    def save_hitl_event(self, event: HITLEvent, user_id: str) -> bool:
        """Stores a human intervention event strictly for the user."""
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

    def get_pending_hitl(self, user_id: str) -> List[HITLEvent]:
        """Retrieves all pending HITL items strictly for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE user_id = ? AND status = 'PENDING' ORDER BY created_at ASC", (user_id,))
            rows = cursor.fetchall()
            return [
                HITLEvent(
                    event_id=r["event_id"],
                    user_id=user_id,
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

    def get_hitl_event(self, event_id: str, user_id: str) -> Optional[HITLEvent]:
        """Retrieves a single HITL event by ID strictly for the specified user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE event_id = ? AND user_id = ? LIMIT 1", (event_id, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            return HITLEvent(
                event_id=row["event_id"],
                user_id=user_id,
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

    def resolve_hitl_event(self, event_id: str, user_answer: str, user_id: str) -> bool:
        """Atomically resolves a pending HITL question strictly for the user."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.now().isoformat()
                cursor.execute("""
                UPDATE hitl_events SET status = 'RESOLVED', user_answer = ?, resolved_at = ?
                WHERE event_id = ? AND user_id = ? AND status = 'PENDING'
                """, (user_answer, now_str, event_id, user_id))
                conn.commit()
                return cursor.rowcount > 0

    # =========================================================================
    # Outreach & Email Operations (Multi-Tenant)
    # =========================================================================
    def save_outreach(self, record: OutreachRecord, user_id: str) -> bool:
        """Saves a multi-channel outreach draft strictly for the user."""
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

    def get_outreach(self, job_id: str, user_id: str) -> List[OutreachRecord]:
        """Retrieves all outreach records for a specific job strictly for the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM outreach_records WHERE job_id = ? AND user_id = ?", (job_id, user_id))
            rows = cursor.fetchall()
            return [
                OutreachRecord(
                    outreach_id=r["outreach_id"],
                    user_id=user_id,
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

    def save_email(self, email: EmailMessage, user_id: str) -> bool:
        """Stores classified inbound recruiter email strictly for the user."""
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

    def get_emails(self, user_id: str) -> List[EmailMessage]:
        """Retrieves all tracked recruiter communications strictly for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM emails WHERE user_id = ? ORDER BY received_at DESC", (user_id,))
            rows = cursor.fetchall()
            return [
                EmailMessage(
                    message_id=r["message_id"],
                    user_id=user_id,
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
    # Job Checkpoint Recovery (Multi-Tenant)
    # =========================================================================
    def save_checkpoint(self, checkpoint: JobCheckpoint, user_id: str) -> bool:
        """Saves current automation execution step strictly for the user."""
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

    def get_checkpoint(self, job_id: str, user_id: str) -> Optional[JobCheckpoint]:
        """Retrieves active checkpoint strictly for the user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM job_checkpoints WHERE job_id = ? AND user_id = ?", (job_id, user_id))
            row = cursor.fetchone()
            if row:
                return JobCheckpoint(
                    job_id=row["job_id"],
                    user_id=user_id,
                    current_step=row["current_step"],
                    total_steps=row["total_steps"],
                    filled_inputs=json.loads(row["filled_inputs"]),
                    last_url=row["last_url"],
                    screenshot_path=row["screenshot_path"],
                    updated_at=row["updated_at"]
                )
            return None

    def delete_checkpoint(self, job_id: str, user_id: str):
        """Deletes checkpoint strictly for the user."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM job_checkpoints WHERE job_id = ? AND user_id = ?", (job_id, user_id))
                conn.commit()

    # =========================================================================
    # Funnel Analytics (Multi-Tenant)
    # =========================================================================
    def get_funnel_metrics(self, user_id: str) -> Dict[str, Any]:
        """Computes conversion funnel metrics strictly for the authenticated tenant."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM jobs WHERE user_id = ?", (user_id,))
            total_sourced = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as applied FROM jobs WHERE user_id = ? AND status IN ('SUBMITTED', 'RESPONDED', 'INTERVIEW', 'OFFER')", (user_id,))
            total_applied = cursor.fetchone()["applied"]

            cursor.execute("SELECT COUNT(*) as interviews FROM jobs WHERE user_id = ? AND status = 'INTERVIEW'", (user_id,))
            interviews = cursor.fetchone()["interviews"]

            cursor.execute("SELECT COUNT(*) as offers FROM jobs WHERE user_id = ? AND status = 'OFFER'", (user_id,))
            offers = cursor.fetchone()["offers"]

            cursor.execute("SELECT COUNT(*) as responses FROM emails WHERE user_id = ? AND intent IN ('INTERVIEW_INVITE', 'ASSESSMENT')", (user_id,))
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

