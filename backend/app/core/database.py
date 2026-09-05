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
    ApplicationStatus, OutreachRecord, OutreachChannel, EmailMessage, JobCheckpoint,
    ApplyLedgerEntry, ApplyLedgerStatus,
    Organization, Membership, AdminAuditLog, OrgRole,
    AnalyticsEvent, ABExperiment, ABVariant, ABAssignment, ConversionSignal
)
from app.core.db_adapter import DatabaseAdapter
from app.core.credential_vault import cred_vault

SAMPLE_PREVIEW_JOBS_CATALOG: Dict[str, Dict[str, Any]] = {
    "sample_swiggy_01": {
        "company": "Swiggy",
        "title": "SDE II (Logistics & Delivery Platform)",
        "location": "Bangalore, 2 yrs exp",
        "platform": "Naukri",
        "url": "https://www.naukri.com/swiggy-sde-2",
        "description": "Building high-throughput, low-latency microservices with Python, Go, and Kafka for Swiggy's delivery dispatch engine.",
        "salary_range": "₹28-35 LPA",
        "match_score": 0.94,
        "priority_score": 92.0,
        "status": ApplicationStatus.DISCOVERED
    },
    "sample_razorpay_02": {
        "company": "Razorpay",
        "title": "Backend Eng. (Payments Settlements)",
        "location": "Remote (India)",
        "platform": "Instahyre",
        "url": "https://www.instahyre.com/razorpay-backend-eng",
        "description": "Scalable payment ledger systems, idempotent API handling, and distributed database transactions.",
        "salary_range": "₹24-30 LPA",
        "match_score": 0.91,
        "priority_score": 89.0,
        "status": ApplicationStatus.DISCOVERED
    },
    "sample_zepto_03": {
        "company": "Zepto",
        "title": "Lead Eng. (Realtime Search & Indexing)",
        "location": "Mumbai / Bangalore",
        "platform": "Cuvette",
        "url": "https://cuvette.tech/zepto-lead-eng",
        "description": "Sub-10ms search indexing, catalog ranking algorithms, and elastic search clusters.",
        "salary_range": "₹40-50 LPA",
        "match_score": 0.91,
        "priority_score": 90.0,
        "status": ApplicationStatus.QUEUED
    },
    "sample_postman_04": {
        "company": "Postman",
        "title": "Product Engineer (API Tooling)",
        "location": "Bangalore",
        "platform": "Cutshort",
        "url": "https://cutshort.io/postman-product-eng",
        "description": "Building next-generation API testing, collaboration, and developer tooling workflows.",
        "salary_range": "₹32-38 LPA",
        "match_score": 0.88,
        "priority_score": 86.0,
        "status": ApplicationStatus.SUBMITTED
    },
    "sample_cred_05": {
        "company": "CRED",
        "title": "UI/UX Full Stack SDE (Growth)",
        "location": "Bangalore",
        "platform": "Instahyre",
        "url": "https://www.instahyre.com/cred-fullstack-sde",
        "description": "High-fidelity micro-interactions, responsive frontend architecture, and robust Python backend services.",
        "salary_range": "₹30-45 LPA",
        "match_score": 0.88,
        "priority_score": 87.0,
        "status": ApplicationStatus.INTERVIEW,
        "notes": "https://meet.google.com/abc-defg-hij"
    },
    "sample_flipkart_06": {
        "company": "Flipkart",
        "title": "SDE-3 (Distributed Systems Architecture)",
        "location": "Bangalore",
        "platform": "Naukri",
        "url": "https://www.naukri.com/flipkart-sde-3",
        "description": "High-scale inventory ordering systems, async message buses, and fault-tolerant architecture.",
        "salary_range": "₹35-50 LPA",
        "match_score": 0.88,
        "priority_score": 88.0,
        "status": ApplicationStatus.INTERVIEW,
        "notes": "Round 2 System Design Scheduled"
    },
    "sample_phonepe_07": {
        "company": "PhonePe",
        "title": "SDE-3 (UPI Core High-Throughput Engine)",
        "location": "Bangalore / Pune",
        "platform": "Naukri",
        "url": "https://www.naukri.com/phonepe-sde-3",
        "description": "High-concurrency payment processing, distributed locks, and real-time bank gateway integration.",
        "salary_range": "₹35 LPA",
        "match_score": 0.89,
        "priority_score": 89.0,
        "status": ApplicationStatus.OFFER,
        "notes": "Official offer letter received"
    }
}


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
        conn = sqlite3.connect(str(self.db_path), timeout=15.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        conn.execute("PRAGMA cache_size = -64000;")
        conn.execute("PRAGMA mmap_size = 268435456;")
        conn.execute("PRAGMA temp_store = MEMORY;")
        return conn

    def _init_pragmas(self):
        with sqlite3.connect(str(self.db_path), timeout=15.0) as conn:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.execute("PRAGMA busy_timeout = 10000;")
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
                    fingerprint TEXT NOT NULL,
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

                # Check if legacy table has global UNIQUE constraint on fingerprint
                cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='jobs';")
                schema_row = cursor.fetchone()
                if schema_row and "fingerprint TEXT UNIQUE" in schema_row["sql"]:
                    cursor.execute("PRAGMA foreign_keys=OFF;")
                    cursor.execute("""
                    CREATE TABLE IF NOT EXISTS jobs_migration_tmp (
                        job_id TEXT PRIMARY KEY,
                        user_id TEXT NOT NULL DEFAULT 'default',
                        fingerprint TEXT NOT NULL,
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
                    );
                    """)
                    cursor.execute("""
                    INSERT OR IGNORE INTO jobs_migration_tmp SELECT 
                        job_id, user_id, fingerprint, platform, company, title, location, url,
                        description, salary_range, seniority_level, posted_date, match_score,
                        priority_score, match_reasons, missing_skills, status, submission_mode,
                        applied_at, application_id, confirmation_screenshot_path, notes
                    FROM jobs;
                    """)
                    cursor.execute("DROP TABLE jobs;")
                    cursor.execute("ALTER TABLE jobs_migration_tmp RENAME TO jobs;")
                    cursor.execute("PRAGMA foreign_keys=ON;")

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
                cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_jobs_user_fingerprint ON jobs(user_id, fingerprint);")
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
                    screenshot_path TEXT,
                    dom_snapshot TEXT,
                    field_selector TEXT,
                    created_at TEXT NOT NULL,
                    resolved_at TEXT
                )
                """)
                self._ensure_columns(conn, "hitl_events", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'",
                    "screenshot_path": "TEXT",
                    "dom_snapshot": "TEXT",
                    "field_selector": "TEXT",
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

                # 12. Login Attempts Table (Brute-Force & Lockout Defense)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    email TEXT NOT NULL,
                    ip TEXT NOT NULL,
                    attempted_at TEXT NOT NULL,
                    success INTEGER NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_email ON login_attempts(email);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_login_attempts_ip ON login_attempts(ip);")

                # 13. Apply Ledger Table (Idempotent Audit Ledger)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS apply_ledger (
                    ledger_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    job_id TEXT NOT NULL,
                    job_fingerprint TEXT NOT NULL,
                    status TEXT NOT NULL,
                    attempt_count INTEGER DEFAULT 1,
                    max_retries INTEGER DEFAULT 3,
                    last_error_category TEXT,
                    last_error_message TEXT,
                    confirmation_id TEXT,
                    screenshot_path TEXT,
                    idempotency_key TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
                self._ensure_columns(conn, "apply_ledger", {
                    "user_id": "TEXT NOT NULL DEFAULT 'default'",
                    "job_fingerprint": "TEXT NOT NULL DEFAULT ''",
                    "attempt_count": "INTEGER DEFAULT 1",
                    "max_retries": "INTEGER DEFAULT 3",
                    "last_error_category": "TEXT",
                    "last_error_message": "TEXT",
                    "confirmation_id": "TEXT",
                    "screenshot_path": "TEXT",
                    "idempotency_key": "TEXT"
                })
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_apply_ledger_user_job ON apply_ledger(user_id, job_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_apply_ledger_user_fingerprint ON apply_ledger(user_id, job_fingerprint);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_apply_ledger_status ON apply_ledger(status);")

                self._ensure_columns(conn, "users", {
                    "email_verified": "INTEGER DEFAULT 0"
                })

                # 14. Organizations Table (SaaS Multi-Tenancy)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS organizations (
                    org_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    owner_id TEXT NOT NULL,
                    plan_tier TEXT DEFAULT 'FREE',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_organizations_slug ON organizations(slug);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_organizations_owner_id ON organizations(owner_id);")

                # 15. Memberships Table (Org Roles & RBAC)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS memberships (
                    membership_id TEXT PRIMARY KEY,
                    org_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL DEFAULT 'MEMBER',
                    invited_by TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    UNIQUE(org_id, user_id)
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memberships_user_id ON memberships(user_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_memberships_org_id ON memberships(org_id);")

                # 16. Admin Audit Logs Table (Admin Security & Impersonation Tracking)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_audit_logs (
                    log_id TEXT PRIMARY KEY,
                    admin_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    target_user_id TEXT,
                    target_org_id TEXT,
                    ip_address TEXT,
                    details JSON NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_admin_id ON admin_audit_logs(admin_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_admin_audit_logs_action ON admin_audit_logs(action);")

                # 15. Idempotency Keys Table
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS idempotency_keys (
                    idempotency_key TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL DEFAULT 'default',
                    method TEXT NOT NULL,
                    path TEXT NOT NULL,
                    request_hash TEXT NOT NULL,
                    status_code INTEGER,
                    response_headers JSON,
                    response_body TEXT,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    expires_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_idempotency_keys_expires ON idempotency_keys(expires_at);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_idempotency_keys_user ON idempotency_keys(user_id, idempotency_key);")

                # 16. MFA Credentials Table (Epic F)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS mfa_credentials (
                    user_id TEXT PRIMARY KEY,
                    secret TEXT NOT NULL,
                    backup_codes JSON NOT NULL,
                    is_enabled BOOLEAN NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_mfa_credentials_user ON mfa_credentials(user_id);")

                # 17. User Sessions Table (Epic F)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    token_jti TEXT NOT NULL,
                    ip_address TEXT,
                    user_agent TEXT,
                    device_name TEXT,
                    created_at TEXT NOT NULL,
                    last_active TEXT NOT NULL,
                    is_active BOOLEAN NOT NULL DEFAULT 1
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_user ON user_sessions(user_id, is_active);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_sessions_jti ON user_sessions(token_jti);")

                # 18. Security Audit Logs Table - Append-Only (Epic F)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS security_audit_logs (
                    log_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    event_type TEXT NOT NULL,
                    severity TEXT NOT NULL DEFAULT 'INFO',
                    ip_address TEXT,
                    user_agent TEXT,
                    details JSON NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_audit_user ON security_audit_logs(user_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_audit_event ON security_audit_logs(event_type);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_audit_severity ON security_audit_logs(severity);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_sec_audit_created ON security_audit_logs(created_at DESC);")

                # 19. Analytics Events Warehouse Table (Epic H)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS analytics_events (
                    event_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    properties JSON NOT NULL,
                    created_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_analytics_events_user_type_date ON analytics_events(user_id, event_type, created_at);")

                # 20. A/B Testing Experiments Table (Epic H)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS ab_experiments (
                    experiment_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    description TEXT,
                    variants JSON NOT NULL,
                    status TEXT DEFAULT 'ACTIVE',
                    created_at TEXT NOT NULL,
                    ended_at TEXT
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ab_experiments_user ON ab_experiments(user_id, status);")

                # 21. A/B Testing Assignments Table (Epic H)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS ab_assignments (
                    assignment_id TEXT PRIMARY KEY,
                    experiment_id TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    variant TEXT NOT NULL,
                    converted INTEGER DEFAULT 0,
                    converted_at TEXT,
                    assigned_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_ab_assignments_exp_user_entity ON ab_assignments(experiment_id, user_id, entity_id);")

                # 22. Conversion Signals & Dynamic Weights Table (Epic H)
                cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversion_signals (
                    signal_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    feature_type TEXT NOT NULL,
                    feature_key TEXT NOT NULL,
                    sample_count INTEGER DEFAULT 0,
                    callback_count INTEGER DEFAULT 0,
                    conversion_rate REAL DEFAULT 0.0,
                    weight_multiplier REAL DEFAULT 1.0,
                    updated_at TEXT NOT NULL
                )
                """)
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_conv_signals_user_feat ON conversion_signals(user_id, feature_type, feature_key);")

                # High-traffic compound indexes for query tuning
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_emails_user_received ON emails(user_id, received_at DESC);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_hitl_user_status ON hitl_events(user_id, status);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_outreach_user_job ON outreach_records(user_id, job_id);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_user_applied ON jobs(user_id, applied_at DESC);")

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
                    INSERT INTO users (user_id, email, password_hash, full_name, role, is_active, email_verified, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        user.user_id,
                        user.email.lower().strip(),
                        user.password_hash,
                        user.full_name,
                        user.role.value if hasattr(user.role, 'value') else str(user.role),
                        1 if user.is_active else 0,
                        1 if user.email_verified else 0,
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
                email_verified=bool(row["email_verified"]) if "email_verified" in row.keys() else False,
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
                email_verified=bool(row["email_verified"]) if "email_verified" in row.keys() else False,
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

    def prune_revoked_tokens(self) -> int:
        """Removes expired tokens from the revocation blacklist."""
        now_str = datetime.now().isoformat()
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM revoked_tokens WHERE expires_at != '' AND expires_at < ?", (now_str,))
                deleted = cursor.rowcount
                conn.commit()
                return deleted

    def record_login_attempt(self, email: str, ip: str, success: bool) -> None:
        """Records an authentication attempt for lockout and brute-force tracking."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT INTO login_attempts (email, ip, attempted_at, success)
                VALUES (?, ?, ?, ?)
                """, (email.lower().strip(), ip, datetime.now().isoformat(), 1 if success else 0))
                conn.commit()

    def check_login_lockout(self, email: str, ip: str, max_failures: int = 5, lockout_minutes: int = 15) -> bool:
        """Returns True if email or IP has exceeded consecutive failure threshold."""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(minutes=lockout_minutes)).isoformat()
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT success FROM login_attempts
            WHERE (email = ? OR ip = ?) AND attempted_at >= ?
            ORDER BY attempted_at DESC
            LIMIT ?
            """, (email.lower().strip(), ip, cutoff, max_failures))
            rows = cursor.fetchall()
            if len(rows) >= max_failures and all(r["success"] == 0 for r in rows):
                return True
            return False

    def set_email_verified(self, user_id: str, verified: bool = True) -> bool:
        """Marks user email as verified."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "UPDATE users SET email_verified = ?, updated_at = ? WHERE user_id = ?",
                    (1 if verified else 0, datetime.now().isoformat(), user_id)
                )
                conn.commit()
                return cursor.rowcount > 0

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
        """Inserts or updates a job opportunity strictly for the user with tenant-isolated deduplication."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                # Check if this specific user already has this job
                cursor.execute(
                    "SELECT job_id FROM jobs WHERE user_id = ? AND (job_id = ? OR fingerprint = ?) LIMIT 1",
                    (user_id, job.job_id, job.fingerprint)
                )
                existing = cursor.fetchone()
                target_job_id = existing["job_id"] if existing else job.job_id
                job.job_id = target_job_id
                job.user_id = user_id

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
                INSERT INTO jobs (
                    job_id, user_id, fingerprint, platform, company, title, location, url,
                    description, salary_range, seniority_level, posted_date, match_score,
                    priority_score, match_reasons, missing_skills, status, submission_mode,
                    applied_at, application_id, confirmation_screenshot_path, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(job_id) DO UPDATE SET
                    user_id=excluded.user_id,
                    fingerprint=excluded.fingerprint,
                    platform=excluded.platform,
                    company=excluded.company,
                    title=excluded.title,
                    location=excluded.location,
                    url=excluded.url,
                    description=excluded.description,
                    salary_range=excluded.salary_range,
                    seniority_level=excluded.seniority_level,
                    posted_date=excluded.posted_date,
                    match_score=excluded.match_score,
                    priority_score=excluded.priority_score,
                    match_reasons=excluded.match_reasons,
                    missing_skills=excluded.missing_skills,
                    status=excluded.status,
                    submission_mode=excluded.submission_mode,
                    applied_at=excluded.applied_at,
                    application_id=excluded.application_id,
                    confirmation_screenshot_path=excluded.confirmation_screenshot_path,
                    notes=excluded.notes
                """, (
                    target_job_id,
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
                    notes_to_save
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
        """Retrieves a single job by ID strictly for the specified user with self-healing preview resolution."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM jobs WHERE job_id = ? AND user_id = ? LIMIT 1", (job_id, user_id))
            row = cursor.fetchone()
            if row:
                return self._row_to_job(row)

        # Self-healing fallback for preview job leads
        if job_id in SAMPLE_PREVIEW_JOBS_CATALOG:
            raw = SAMPLE_PREVIEW_JOBS_CATALOG[job_id]
            seed_job = JobListing(
                job_id=job_id,
                user_id=user_id,
                fingerprint=f"fp_{job_id}_{user_id}",
                platform=raw["platform"],
                company=raw["company"],
                title=raw["title"],
                location=raw["location"],
                url=raw["url"],
                description=raw["description"],
                salary_range=raw.get("salary_range"),
                match_score=raw.get("match_score", 0.9),
                priority_score=raw.get("priority_score", 88.0),
                status=raw.get("status", ApplicationStatus.DISCOVERED),
                notes=raw.get("notes", "")
            )
            self.save_job(seed_job, user_id=user_id)
            return seed_job

        return None

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
        raw_notes = r["notes"] or ""
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
            created_at=extracted_created_at,
            interview_date=extracted_interview_date,
            application_id=r["application_id"] if "application_id" in keys else None,
            confirmation_screenshot_path=r["confirmation_screenshot_path"] if "confirmation_screenshot_path" in keys else None,
            notes=clean_notes
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
                    input_type, options, ai_suggested_draft, user_answer, status,
                    screenshot_path, dom_snapshot, field_selector, created_at, resolved_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    event.screenshot_path,
                    event.dom_snapshot,
                    event.field_selector,
                    event.created_at,
                    event.resolved_at
                ))
                conn.commit()
                return True

    def _row_to_hitl_event(self, r: sqlite3.Row, user_id: str) -> HITLEvent:
        keys = r.keys()
        return HITLEvent(
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
            screenshot_path=r["screenshot_path"] if "screenshot_path" in keys else None,
            dom_snapshot=r["dom_snapshot"] if "dom_snapshot" in keys else None,
            field_selector=r["field_selector"] if "field_selector" in keys else None,
            created_at=r["created_at"],
            resolved_at=r["resolved_at"] if "resolved_at" in keys else None
        )

    def get_pending_hitl(self, user_id: str) -> List[HITLEvent]:
        """Retrieves all pending HITL items strictly for a user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE user_id = ? AND status = 'PENDING' ORDER BY created_at ASC", (user_id,))
            rows = cursor.fetchall()
            return [self._row_to_hitl_event(r, user_id) for r in rows]

    get_pending_hitl_events = get_pending_hitl

    def get_hitl_event(self, event_id: str, user_id: str) -> Optional[HITLEvent]:
        """Retrieves a single HITL event by ID strictly for the specified user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM hitl_events WHERE event_id = ? AND user_id = ? LIMIT 1", (event_id, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_hitl_event(row, user_id)

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
    # Apply Ledger Operations (Multi-Tenant)
    # =========================================================================
    def save_apply_ledger_entry(self, entry: ApplyLedgerEntry, user_id: str) -> bool:
        """Saves or updates an idempotent apply ledger record."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                INSERT OR REPLACE INTO apply_ledger (
                    ledger_id, user_id, job_id, job_fingerprint, status,
                    attempt_count, max_retries, last_error_category, last_error_message,
                    confirmation_id, screenshot_path, idempotency_key, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.ledger_id,
                    user_id,
                    entry.job_id,
                    entry.job_fingerprint,
                    entry.status.value if hasattr(entry.status, "value") else str(entry.status),
                    entry.attempt_count,
                    entry.max_retries,
                    entry.last_error_category,
                    entry.last_error_message,
                    entry.confirmation_id,
                    entry.screenshot_path,
                    entry.idempotency_key,
                    entry.created_at,
                    entry.updated_at
                ))
                conn.commit()
                return True

    def _row_to_apply_ledger(self, r: sqlite3.Row) -> ApplyLedgerEntry:
        keys = r.keys()
        raw_status = r["status"]
        status_val = ApplyLedgerStatus.INITIATED
        for st in ApplyLedgerStatus:
            if st.value == raw_status:
                status_val = st
                break

        return ApplyLedgerEntry(
            ledger_id=r["ledger_id"],
            user_id=r["user_id"] if "user_id" in keys else "default",
            job_id=r["job_id"],
            job_fingerprint=r["job_fingerprint"],
            status=status_val,
            attempt_count=r["attempt_count"] if "attempt_count" in keys else 1,
            max_retries=r["max_retries"] if "max_retries" in keys else 3,
            last_error_category=r["last_error_category"] if "last_error_category" in keys else None,
            last_error_message=r["last_error_message"] if "last_error_message" in keys else None,
            confirmation_id=r["confirmation_id"] if "confirmation_id" in keys else None,
            screenshot_path=r["screenshot_path"] if "screenshot_path" in keys else None,
            idempotency_key=r["idempotency_key"] if "idempotency_key" in keys else None,
            created_at=r["created_at"],
            updated_at=r["updated_at"]
        )

    def get_apply_ledger_entry(self, ledger_id: str, user_id: str) -> Optional[ApplyLedgerEntry]:
        """Retrieves a single ledger entry by ledger ID strictly for user."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM apply_ledger WHERE ledger_id = ? AND user_id = ? LIMIT 1", (ledger_id, user_id))
            row = cursor.fetchone()
            return self._row_to_apply_ledger(row) if row else None

    def get_active_ledger_by_fingerprint(self, fingerprint: str, user_id: str) -> Optional[ApplyLedgerEntry]:
        """Finds most recent ledger record for a job fingerprint."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM apply_ledger 
            WHERE job_fingerprint = ? AND user_id = ? 
            ORDER BY updated_at DESC LIMIT 1
            """, (fingerprint, user_id))
            row = cursor.fetchone()
            return self._row_to_apply_ledger(row) if row else None

    def get_ledger_for_job(self, job_id: str, user_id: str) -> Optional[ApplyLedgerEntry]:
        """Finds most recent ledger record for a job ID."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM apply_ledger 
            WHERE job_id = ? AND user_id = ? 
            ORDER BY updated_at DESC LIMIT 1
            """, (job_id, user_id))
            row = cursor.fetchone()
            return self._row_to_apply_ledger(row) if row else None

    def list_user_apply_ledger(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[ApplyLedgerEntry]:
        """Lists ledger history for a user with optional status filtering."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT * FROM apply_ledger WHERE user_id = ?"
            params: list = [user_id]
            if status:
                query += " AND status = ?"
                params.append(status)
            query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_apply_ledger(r) for r in rows]

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

    # =========================================================================
    # SaaS Organization & Team Management
    # =========================================================================
    def create_organization(self, org: Organization) -> bool:
        """Creates a new organization."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO organizations (org_id, name, slug, owner_id, plan_tier, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """, (
                        org.org_id,
                        org.name,
                        org.slug.lower().strip(),
                        org.owner_id,
                        org.plan_tier,
                        org.created_at,
                        org.updated_at
                    ))
                    conn.commit()
                    return True
                except Exception:
                    return False

    def get_organization(self, org_id: str) -> Optional[Organization]:
        """Retrieves an organization by its unique org_id."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE org_id = ?", (org_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Organization(
                org_id=row["org_id"],
                name=row["name"],
                slug=row["slug"],
                owner_id=row["owner_id"],
                plan_tier=row["plan_tier"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        """Retrieves an organization by its slug."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM organizations WHERE slug = ?", (slug.lower().strip(),))
            row = cursor.fetchone()
            if not row:
                return None
            return Organization(
                org_id=row["org_id"],
                name=row["name"],
                slug=row["slug"],
                owner_id=row["owner_id"],
                plan_tier=row["plan_tier"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def list_user_organizations(self, user_id: str) -> List[Dict[str, Any]]:
        """Lists all organizations a user belongs to, including their membership role."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT o.org_id, o.name, o.slug, o.owner_id, o.plan_tier, o.created_at, m.role
            FROM organizations o
            JOIN memberships m ON o.org_id = m.org_id
            WHERE m.user_id = ?
            ORDER BY o.created_at DESC
            """, (user_id,))
            return [dict(r) for r in cursor.fetchall()]

    def update_organization(self, org_id: str, name: Optional[str] = None, plan_tier: Optional[str] = None) -> bool:
        """Updates organization name or plan tier."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                now_str = datetime.now().isoformat()
                if name is not None and plan_tier is not None:
                    cursor.execute("UPDATE organizations SET name = ?, plan_tier = ?, updated_at = ? WHERE org_id = ?", (name, plan_tier, now_str, org_id))
                elif name is not None:
                    cursor.execute("UPDATE organizations SET name = ?, updated_at = ? WHERE org_id = ?", (name, now_str, org_id))
                elif plan_tier is not None:
                    cursor.execute("UPDATE organizations SET plan_tier = ?, updated_at = ? WHERE org_id = ?", (plan_tier, now_str, org_id))
                else:
                    return True
                conn.commit()
                return cursor.rowcount > 0

    # =========================================================================
    # Organization Memberships & RBAC
    # =========================================================================
    def add_membership(self, membership: Membership) -> bool:
        """Adds or updates a user's membership in an organization."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO memberships (membership_id, org_id, user_id, role, invited_by, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(org_id, user_id) DO UPDATE SET
                        role = excluded.role,
                        updated_at = excluded.updated_at
                    """, (
                        membership.membership_id,
                        membership.org_id,
                        membership.user_id,
                        membership.role.value if hasattr(membership.role, 'value') else str(membership.role),
                        membership.invited_by,
                        membership.created_at,
                        membership.updated_at
                    ))
                    conn.commit()
                    return True
                except Exception:
                    return False

    def get_membership(self, org_id: str, user_id: str) -> Optional[Membership]:
        """Gets membership details for a user in an organization."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM memberships WHERE org_id = ? AND user_id = ?", (org_id, user_id))
            row = cursor.fetchone()
            if not row:
                return None
            return Membership(
                membership_id=row["membership_id"],
                org_id=row["org_id"],
                user_id=row["user_id"],
                role=OrgRole(row["role"]),
                invited_by=row["invited_by"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )

    def list_org_members(self, org_id: str) -> List[Dict[str, Any]]:
        """Lists all members of an organization with profile and role details."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT m.membership_id, m.org_id, m.user_id, u.email, u.full_name, m.role, m.created_at
            FROM memberships m
            JOIN users u ON m.user_id = u.user_id
            WHERE m.org_id = ?
            ORDER BY m.created_at ASC
            """, (org_id,))
            return [dict(r) for r in cursor.fetchall()]

    def remove_membership(self, org_id: str, user_id: str) -> bool:
        """Removes a user's membership from an organization."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("DELETE FROM memberships WHERE org_id = ? AND user_id = ?", (org_id, user_id))
                conn.commit()
                return cursor.rowcount > 0

    def update_member_role(self, org_id: str, user_id: str, role: str) -> bool:
        """Updates a user's role within an organization."""
        with self._lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                UPDATE memberships SET role = ?, updated_at = ?
                WHERE org_id = ? AND user_id = ?
                """, (role, datetime.now().isoformat(), org_id, user_id))
                conn.commit()
                return cursor.rowcount > 0

    # =========================================================================
    # Admin Panel, Metrics & Impersonation Audit
    # =========================================================================
    def log_admin_action(self, log_entry: AdminAuditLog) -> bool:
        """Records an admin action or impersonation event to the audit log."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO admin_audit_logs (log_id, admin_id, action, target_user_id, target_org_id, ip_address, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        log_entry.log_id,
                        log_entry.admin_id,
                        log_entry.action,
                        log_entry.target_user_id,
                        log_entry.target_org_id,
                        log_entry.ip_address,
                        json.dumps(log_entry.details),
                        log_entry.created_at
                    ))
                    conn.commit()
                    return True
                except Exception:
                    return False

    def list_admin_audit_logs(self, limit: int = 50, offset: int = 0) -> List[AdminAuditLog]:
        """Retrieves paginated audit log entries."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT * FROM admin_audit_logs
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
            """, (limit, offset))
            results = []
            for r in cursor.fetchall():
                results.append(AdminAuditLog(
                    log_id=r["log_id"],
                    admin_id=r["admin_id"],
                    action=r["action"],
                    target_user_id=r["target_user_id"],
                    target_org_id=r["target_org_id"],
                    ip_address=r["ip_address"],
                    details=json.loads(r["details"]) if r["details"] else {},
                    created_at=r["created_at"]
                ))
            return results

    def list_all_users(self, limit: int = 50, offset: int = 0, search: Optional[str] = None) -> List[Dict[str, Any]]:
        """Lists users for the admin panel with optional search by email or name."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if search:
                term = f"%{search.lower().strip()}%"
                cursor.execute("""
                SELECT user_id, email, full_name, role, is_active, email_verified, created_at, updated_at
                FROM users
                WHERE LOWER(email) LIKE ? OR LOWER(full_name) LIKE ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """, (term, term, limit, offset))
            else:
                cursor.execute("""
                SELECT user_id, email, full_name, role, is_active, email_verified, created_at, updated_at
                FROM users
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """, (limit, offset))
            return [dict(r) for r in cursor.fetchall()]

    def count_all_users(self, search: Optional[str] = None) -> int:
        """Counts total users matching optional search criteria."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if search:
                term = f"%{search.lower().strip()}%"
                cursor.execute("SELECT COUNT(*) as total FROM users WHERE LOWER(email) LIKE ? OR LOWER(full_name) LIKE ?", (term, term))
            else:
                cursor.execute("SELECT COUNT(*) as total FROM users")
            return cursor.fetchone()["total"]

    def list_all_organizations(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """Lists all organizations with member counts."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT o.org_id, o.name, o.slug, o.owner_id, o.plan_tier, o.created_at,
                   COUNT(m.user_id) as member_count
            FROM organizations o
            LEFT JOIN memberships m ON o.org_id = m.org_id
            GROUP BY o.org_id
            ORDER BY o.created_at DESC
            LIMIT ? OFFSET ?
            """, (limit, offset))
            return [dict(r) for r in cursor.fetchall()]

    def count_all_organizations(self) -> int:
        """Counts total organizations."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM organizations")
            return cursor.fetchone()["total"]

    def get_admin_system_metrics(self) -> Dict[str, Any]:
        """Calculates global SaaS platform metrics for admin dashboard."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as c FROM users")
            total_users = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM jobs")
            total_jobs = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM apply_ledger WHERE status = 'SUBMITTED'")
            total_applications = cursor.fetchone()["c"]

            cursor.execute("SELECT COUNT(*) as c FROM organizations")
            total_organizations = cursor.fetchone()["c"]

            cursor.execute("SELECT role, COUNT(*) as c FROM users GROUP BY role")
            active_subscriptions = {"FREE": 0, "PRO": 0, "ELITE": 0, "ADMIN": 0}
            for row in cursor.fetchall():
                role_val = row["role"]
                if role_val in active_subscriptions:
                    active_subscriptions[role_val] = row["c"]

            return {
                "total_users": total_users,
                "total_jobs": total_jobs,
                "total_applications": total_applications,
                "active_subscriptions": active_subscriptions,
                "total_organizations": total_organizations
            }

    # =========================================================================
    # GDPR Data Portability & Erasure
    # =========================================================================
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """Generates comprehensive GDPR Article 20 data portability export bundle."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, email, full_name, role, is_active, email_verified, created_at, updated_at FROM users WHERE user_id = ?", (user_id,))
            user_row = cursor.fetchone()
            user_info = dict(user_row) if user_row else {}

            profile = self.get_profile(user_id)
            profile_dict = profile.dict() if profile else {}

            jobs = [j.dict() for j in self.get_jobs(user_id)]
            vault_entries = [v.dict() for v in self.get_vault_entries(user_id)]
            ledger_entries = [l.dict() for l in self.list_user_apply_ledger(user_id, limit=10000)]

            cursor.execute("SELECT * FROM hitl_events WHERE user_id = ?", (user_id,))
            hitl_events = [dict(r) for r in cursor.fetchall()]

            emails = [e.dict() for e in self.get_emails(user_id)]

            cursor.execute("SELECT * FROM outreach_records WHERE user_id = ?", (user_id,))
            outreach_records = [dict(r) for r in cursor.fetchall()]

            orgs = self.list_user_organizations(user_id)

            return {
                "user_id": user_id,
                "exported_at": datetime.now().isoformat(),
                "account": user_info,
                "profile": profile_dict,
                "jobs": jobs,
                "knowledge_vault": vault_entries,
                "apply_ledger": ledger_entries,
                "hitl_events": hitl_events,
                "emails": emails,
                "outreach_records": outreach_records,
                "organizations": orgs
            }

    def hard_delete_user_account(self, user_id: str) -> bool:
        """Executes full GDPR Article 17 hard erasure across all tenant-scoped tables and disk storage."""
        import shutil
        from app.core.config import settings
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM profiles WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM jobs WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM vault WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM apply_ledger WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM hitl_events WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM emails WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM outreach_records WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM user_daily_usage WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM memberships WHERE user_id = ?", (user_id,))
                    cursor.execute("DELETE FROM organizations WHERE owner_id = ?", (user_id,))
                    conn.commit()

                    try:
                        user_storage = Path(settings.BASE_DIR) / "storage" / "users" / user_id
                        if user_storage.exists() and user_storage.is_dir():
                            shutil.rmtree(user_storage, ignore_errors=True)
                    except Exception:
                        pass

                    return True
                except Exception:
                    conn.rollback()
                    return False

    # =========================================================================
    # Idempotency Engine Operations
    # =========================================================================
    def save_idempotency_record(self, record: Dict[str, Any]) -> bool:
        """Persists a pending or completed idempotency record."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO idempotency_keys (
                        idempotency_key, user_id, method, path, request_hash,
                        status_code, response_headers, response_body, status, created_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(idempotency_key) DO UPDATE SET
                        status_code = excluded.status_code,
                        response_headers = excluded.response_headers,
                        response_body = excluded.response_body,
                        status = excluded.status,
                        expires_at = excluded.expires_at
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
                        record.get("created_at", datetime.utcnow().isoformat()),
                        record.get("expires_at", "")
                    ))
                    conn.commit()
                    return True
                except Exception:
                    conn.rollback()
                    return False

    def get_idempotency_record(self, idempotency_key: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
        """Retrieves an active idempotency record by key, verifying tenant isolation."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
            SELECT idempotency_key, user_id, method, path, request_hash,
                   status_code, response_headers, response_body, status, created_at, expires_at
            FROM idempotency_keys
            WHERE idempotency_key = ? AND (user_id = ? OR user_id = 'default')
            """, (idempotency_key, user_id))
            row = cursor.fetchone()
            if not row:
                return None

            try:
                headers = json.loads(row[6]) if row[6] else {}
            except Exception:
                headers = {}

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

    def update_idempotency_record(
        self,
        idempotency_key: str,
        status: str,
        status_code: int,
        response_headers: Dict[str, Any],
        response_body: str
    ) -> bool:
        """Marks an idempotency record as completed with cached response data."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    UPDATE idempotency_keys
                    SET status = ?, status_code = ?, response_headers = ?, response_body = ?
                    WHERE idempotency_key = ?
                    """, (
                        status,
                        status_code,
                        json.dumps(response_headers),
                        response_body,
                        idempotency_key
                    ))
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    return False

    def delete_idempotency_record(self, idempotency_key: str) -> bool:
        """Deletes an idempotency record (e.g., to release a lock on error)."""
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM idempotency_keys WHERE idempotency_key = ?", (idempotency_key,))
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    return False

    def cleanup_expired_idempotency_keys(self) -> int:
        """Purges expired idempotency records from storage."""
        now_iso = datetime.utcnow().isoformat()
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM idempotency_keys WHERE expires_at != '' AND expires_at < ?", (now_iso,))
                    conn.commit()
                    return cursor.rowcount
                except Exception:
                    conn.rollback()
                    return 0

    # =========================================================================
    # Epic F: MFA / TOTP Storage
    # =========================================================================
    def get_mfa_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT user_id, secret, backup_codes, is_enabled, created_at, updated_at FROM mfa_credentials WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            backup_codes = []
            if row[2]:
                try:
                    backup_codes = json.loads(row[2])
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

    def save_mfa_credentials(self, user_id: str, secret: str, backup_codes: List[Dict[str, Any]], is_enabled: bool) -> bool:
        now_str = datetime.now().isoformat()
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO mfa_credentials (user_id, secret, backup_codes, is_enabled, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        secret = excluded.secret,
                        backup_codes = excluded.backup_codes,
                        is_enabled = excluded.is_enabled,
                        updated_at = excluded.updated_at
                    """, (user_id, secret, json.dumps(backup_codes), 1 if is_enabled else 0, now_str, now_str))
                    conn.commit()
                    return True
                except Exception:
                    conn.rollback()
                    return False

    def delete_mfa_credentials(self, user_id: str) -> bool:
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("DELETE FROM mfa_credentials WHERE user_id = ?", (user_id,))
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    return False

    # =========================================================================
    # Epic F: Session & Device Management
    # =========================================================================
    def create_session(self, session: Dict[str, Any]) -> bool:
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO user_sessions (session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        session["session_id"],
                        session["user_id"],
                        session["token_jti"],
                        session.get("ip_address"),
                        session.get("user_agent"),
                        session.get("device_name", "Unknown Device"),
                        session.get("created_at", datetime.now().isoformat()),
                        session.get("last_active", datetime.now().isoformat()),
                        1 if session.get("is_active", True) else 0
                    ))
                    conn.commit()
                    return True
                except Exception:
                    conn.rollback()
                    return False

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active FROM user_sessions WHERE session_id = ?",
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

    def list_user_sessions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if active_only:
                cursor.execute(
                    "SELECT session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active FROM user_sessions WHERE user_id = ? AND is_active = 1 ORDER BY last_active DESC",
                    (user_id,)
                )
            else:
                cursor.execute(
                    "SELECT session_id, user_id, token_jti, ip_address, user_agent, device_name, created_at, last_active, is_active FROM user_sessions WHERE user_id = ? ORDER BY last_active DESC",
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

    def revoke_session(self, session_id: str, user_id: str) -> bool:
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE user_sessions SET is_active = 0 WHERE session_id = ? AND user_id = ?",
                        (session_id, user_id)
                    )
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    return False

    def revoke_all_user_sessions(self, user_id: str, except_jti: Optional[str] = None) -> int:
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    if except_jti:
                        cursor.execute(
                            "UPDATE user_sessions SET is_active = 0 WHERE user_id = ? AND token_jti != ? AND is_active = 1",
                            (user_id, except_jti)
                        )
                    else:
                        cursor.execute(
                            "UPDATE user_sessions SET is_active = 0 WHERE user_id = ? AND is_active = 1",
                            (user_id,)
                        )
                    conn.commit()
                    return cursor.rowcount
                except Exception:
                    conn.rollback()
                    return 0

    def update_session_activity(self, token_jti: str) -> bool:
        now_str = datetime.now().isoformat()
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute(
                        "UPDATE user_sessions SET last_active = ? WHERE token_jti = ? AND is_active = 1",
                        (now_str, token_jti)
                    )
                    conn.commit()
                    return cursor.rowcount > 0
                except Exception:
                    conn.rollback()
                    return False

    # =========================================================================
    # Epic F: Security Audit Logs (Append-Only)
    # =========================================================================
    def insert_security_audit_log(self, log_entry: Dict[str, Any]) -> bool:
        with self._lock:
            with self.get_connection() as conn:
                try:
                    cursor = conn.cursor()
                    cursor.execute("""
                    INSERT INTO security_audit_logs (log_id, user_id, event_type, severity, ip_address, user_agent, details, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
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

    def list_security_audit_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT log_id, user_id, event_type, severity, ip_address, user_agent, details, created_at "
                "FROM security_audit_logs "
                "WHERE (? IS NULL OR user_id = ?) "
                "AND (? IS NULL OR event_type = ?) "
                "AND (? IS NULL OR severity = ?) "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?"
            )
            cursor.execute(query, (user_id, user_id, event_type, event_type, severity, severity, limit, offset))
            rows = cursor.fetchall()
            results = []
            for r in rows:
                details = {}
                if r[6]:
                    try:
                        details = json.loads(r[6])
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

    def count_security_audit_logs(
        self,
        user_id: Optional[str] = None,
        event_type: Optional[str] = None,
        severity: Optional[str] = None
    ) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT COUNT(*) FROM security_audit_logs "
                "WHERE (? IS NULL OR user_id = ?) "
                "AND (? IS NULL OR event_type = ?) "
                "AND (? IS NULL OR severity = ?)"
            )
            cursor.execute(query, (user_id, user_id, event_type, event_type, severity, severity))
            row = cursor.fetchone()
            return row[0] if row else 0

    # =========================================================================
    # Epic H: Analytics Warehouse & Event Streaming
    # =========================================================================
    def record_analytics_event(self, event: AnalyticsEvent) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO analytics_events (event_id, user_id, event_type, entity_type, entity_id, properties, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
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

    def query_analytics_events(
        self,
        user_id: str,
        event_type: Optional[str] = None,
        limit: int = 100
    ) -> List[AnalyticsEvent]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT event_id, user_id, event_type, entity_type, entity_id, properties, created_at "
                "FROM analytics_events "
                "WHERE (user_id = ? OR ? = 'admin') "
                "AND (? IS NULL OR event_type = ?) "
                "ORDER BY created_at DESC LIMIT ?"
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

    # =========================================================================
    # Epic H: A/B Testing Framework
    # =========================================================================
    def create_ab_experiment(self, experiment: ABExperiment) -> str:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO ab_experiments (experiment_id, user_id, name, description, variants, status, created_at, ended_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
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

    def get_ab_experiment(self, experiment_id: str, user_id: str) -> Optional[ABExperiment]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT experiment_id, user_id, name, description, variants, status, created_at, ended_at "
                "FROM ab_experiments "
                "WHERE experiment_id = ? AND (user_id = ? OR ? = 'admin')",
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

    def list_ab_experiments(self, user_id: str) -> List[ABExperiment]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT experiment_id, user_id, name, description, variants, status, created_at, ended_at "
                "FROM ab_experiments "
                "WHERE user_id = ? OR ? = 'admin' "
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
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO ab_assignments (assignment_id, experiment_id, user_id, entity_id, variant, converted, converted_at, assigned_at) "
                "VALUES (?, ?, ?, ?, ?, 0, NULL, ?)",
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

    def get_ab_assignment(self, experiment_id: str, user_id: str, entity_id: str) -> Optional[ABAssignment]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT assignment_id, experiment_id, user_id, entity_id, variant, converted, converted_at, assigned_at "
                "FROM ab_assignments "
                "WHERE experiment_id = ? AND user_id = ? AND entity_id = ?",
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

    def record_ab_conversion(self, experiment_id: str, user_id: str, entity_id: str) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            now_iso = datetime.now().isoformat()
            cursor.execute(
                "UPDATE ab_assignments "
                "SET converted = 1, converted_at = ? "
                "WHERE experiment_id = ? AND user_id = ? AND entity_id = ? AND converted = 0",
                (now_iso, experiment_id, user_id, entity_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def get_ab_experiment_stats(self, experiment_id: str, user_id: str) -> Dict[str, Any]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT variant, COUNT(*), SUM(CASE WHEN converted = 1 THEN 1 ELSE 0 END) "
                "FROM ab_assignments "
                "WHERE experiment_id = ? AND (user_id = ? OR ? = 'admin') "
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

    # =========================================================================
    # Epic H: Conversion Signals & Feedback Loop Weights
    # =========================================================================
    def upsert_conversion_signal(self, signal: ConversionSignal) -> None:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversion_signals (signal_id, user_id, feature_type, feature_key, sample_count, callback_count, conversion_rate, weight_multiplier, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(signal_id) DO UPDATE SET "
                "sample_count = excluded.sample_count, "
                "callback_count = excluded.callback_count, "
                "conversion_rate = excluded.conversion_rate, "
                "weight_multiplier = excluded.weight_multiplier, "
                "updated_at = excluded.updated_at",
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

    def get_conversion_signals(self, user_id: str, feature_type: Optional[str] = None) -> List[ConversionSignal]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            query = (
                "SELECT signal_id, user_id, feature_type, feature_key, sample_count, callback_count, conversion_rate, weight_multiplier, updated_at "
                "FROM conversion_signals "
                "WHERE (user_id = ? OR ? = 'admin') "
                "AND (? IS NULL OR feature_type = ?) "
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



db = DatabaseManager()


def get_db() -> DatabaseAdapter:
    """Returns active database adapter (PostgreSQL if configured, else SQLite WAL engine)."""
    from app.core.settings import settings
    if settings.DATABASE_URL and settings.DATABASE_URL.startswith("postgres"):
        try:
            from app.core.postgres_adapter import PostgresDatabaseAdapter
            return PostgresDatabaseAdapter(settings.DATABASE_URL)
        except Exception:
            return db
    return db

