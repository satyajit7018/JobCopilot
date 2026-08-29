"""
JobCopilot - SQLite Local-First Storage Engine
Handles profiles, knowledge vault entries, job listings, and HITL event logs.
"""

import sqlite3
import json
from typing import List, Dict, Optional, Any
from app.core.config import DB_PATH
from app.core.models import CandidateProfile, VaultEntry, JobListing, HITLEvent, ApplicationStatus


class DatabaseManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._init_db()

    def get_connection(self):
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Profiles Table
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                data JSON NOT NULL,
                updated_at TEXT NOT NULL
            )
            """)

            # Knowledge Vault Table
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

            # Job Listings Table
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
                posted_date TEXT,
                match_score REAL DEFAULT 0.0,
                priority_score REAL DEFAULT 0.0,
                status TEXT NOT NULL,
                applied_at TEXT,
                notes TEXT
            )
            """)

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
                created_at TEXT NOT NULL
            )
            """)
            conn.commit()

    # --- Profile Operations ---
    def save_profile(self, profile: CandidateProfile):
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
        with self.get_connection() as conn:
            cursor = conn.cursor()
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

    # --- Job Operations ---
    def save_job(self, job: JobListing) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute("""
                INSERT OR REPLACE INTO jobs 
                (job_id, fingerprint, platform, company, title, location, url, description, posted_date, match_score, priority_score, status, applied_at, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    job.job_id, job.fingerprint, job.platform, job.company, job.title,
                    job.location, job.url, job.description, job.posted_date,
                    job.match_score, job.priority_score, job.status.value,
                    job.applied_at, job.notes
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
                    description=row["description"],
                    posted_date=row["posted_date"],
                    match_score=row["match_score"],
                    priority_score=row["priority_score"],
                    status=ApplicationStatus(row["status"]),
                    applied_at=row["applied_at"],
                    notes=row["notes"]
                ))
        return jobs

    def update_job_status(self, job_id: str, status: ApplicationStatus, notes: Optional[str] = None):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("UPDATE jobs SET status = ?, notes = ? WHERE job_id = ?", (status.value, notes, job_id))
            conn.commit()

    # --- HITL Event Operations ---
    def save_hitl_event(self, event: HITLEvent):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            INSERT OR REPLACE INTO hitl_events
            (event_id, job_id, company, role_title, question_text, input_type, options, ai_suggested_draft, user_answer, status, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_id, event.job_id, event.company, event.role_title,
                event.question_text, event.input_type, json.dumps(event.options),
                event.ai_suggested_draft, event.user_answer, event.status, event.created_at
            ))
            conn.commit()

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
                    created_at=row["created_at"]
                ))
        return events


db = DatabaseManager()
