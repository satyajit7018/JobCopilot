"""
JobCopilot - GDPR Article 17 Erasure Completeness Test
Verifies that hard_delete_user_account comprehensively purges all user-scoped tables,
retains legal compliance tables (security_audit_logs, user_consents), and prevents
any collateral deletion of other users.
"""

import json
import uuid
from datetime import datetime

from app.core.database import db


def test_gdpr_hard_delete_completeness():
    u_suffix = uuid.uuid4().hex[:8]
    u_id = f"usr_gdpr_u_{u_suffix}"
    u_email = f"gdpr_u_{u_suffix}@example.com"

    v_suffix = uuid.uuid4().hex[:8]
    v_id = f"usr_gdpr_v_{v_suffix}"
    v_email = f"gdpr_v_{v_suffix}@example.com"

    now = datetime.utcnow().isoformat()
    now_date = datetime.utcnow().strftime("%Y-%m-%d")

    # The 20 user-scoped tables that MUST be purged
    PURGED_TABLES = [
        "users",
        "profiles",
        "jobs",
        "vault",
        "apply_ledger",
        "hitl_events",
        "emails",
        "outreach_records",
        "user_daily_usage",
        "memberships",
        "organizations",
        "job_checkpoints",
        "revoked_tokens",
        "idempotency_keys",
        "mfa_credentials",
        "user_sessions",
        "analytics_events",
        "ab_assignments",
        "ab_experiments",
        "conversion_signals",
    ]

    # Tables retained under GDPR Art. 17(3) for legal/compliance proof
    RETAINED_TABLES = [
        "security_audit_logs",
        "user_consents",
    ]

    org_u_id = f"org_u_{u_suffix}"
    org_v_id = f"org_v_{v_suffix}"

    with db.get_connection() as conn:
        cursor = conn.cursor()

        # Seed User U in all 20 purged tables
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (u_id, u_email, "hash_u", now, now),
        )
        cursor.execute(
            "INSERT INTO profiles (id, user_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (f"prof_{u_suffix}", u_id, json.dumps({"skills": ["Python"]}), now),
        )
        cursor.execute(
            "INSERT INTO jobs (job_id, user_id, fingerprint, platform, company, title, location, url, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"job_{u_suffix}", u_id, f"fp_{u_suffix}", "LinkedIn", "TechCorp", "SWE", "Remote", "https://example.com/job", "PENDING"),
        )
        cursor.execute(
            "INSERT INTO vault (qa_id, user_id, slot_type, slot_key, question_pattern, embedding, answer_template, dynamic_variables, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"vlt_{u_suffix}", u_id, "STAR", "lead_team", "tell me about", json.dumps([]), "I led a team", json.dumps({}), now),
        )
        cursor.execute(
            "INSERT INTO apply_ledger (ledger_id, user_id, job_id, job_fingerprint, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"led_{u_suffix}", u_id, f"job_{u_suffix}", f"fp_{u_suffix}", "APPLIED", now, now),
        )
        cursor.execute(
            "INSERT INTO hitl_events (event_id, user_id, job_id, company, role_title, question_text, input_type, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"hitl_{u_suffix}", u_id, f"job_{u_suffix}", "TechCorp", "SWE", "Salary expectation?", "text", "PENDING", now),
        )
        cursor.execute(
            "INSERT INTO emails (message_id, user_id, sender, recipient, subject, body_text, received_at, intent) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"eml_{u_suffix}", u_id, "recruiter@example.com", u_email, "Interview Invitation", "Please reply", now, "INTERVIEW_INVITE"),
        )
        cursor.execute(
            "INSERT INTO outreach_records (outreach_id, user_id, job_id, channel, message_content, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"out_{u_suffix}", u_id, f"job_{u_suffix}", "EMAIL", "Hi, I applied.", "SENT", now),
        )
        cursor.execute(
            "INSERT INTO user_daily_usage (user_id, date, apply_count) VALUES (?, ?, ?)",
            (u_id, now_date, 5),
        )
        cursor.execute(
            "INSERT INTO organizations (org_id, name, slug, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (org_u_id, f"Org {u_suffix}", f"org-{u_suffix}", u_id, now, now),
        )
        cursor.execute(
            "INSERT INTO memberships (membership_id, org_id, user_id, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"mem_{u_suffix}", org_u_id, u_id, "OWNER", now, now),
        )
        cursor.execute(
            "INSERT INTO job_checkpoints (job_id, user_id, current_step, total_steps, filled_inputs, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"job_{u_suffix}", u_id, 2, 5, json.dumps({"q1": "yes"}), now),
        )
        cursor.execute(
            "INSERT INTO revoked_tokens (jti, user_id, revoked_at) VALUES (?, ?, ?)",
            (f"jti_{u_suffix}", u_id, now),
        )
        cursor.execute(
            "INSERT INTO idempotency_keys (idempotency_key, user_id, method, path, request_hash, status, created_at, expires_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (f"idem_{u_suffix}", u_id, "POST", "/apply", "reqhash", "COMPLETED", now, now),
        )
        cursor.execute(
            "INSERT INTO mfa_credentials (user_id, secret, backup_codes, is_enabled, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (u_id, "BASE32SECRET", json.dumps(["code1", "code2"]), 1, now, now),
        )
        cursor.execute(
            "INSERT INTO user_sessions (session_id, user_id, token_jti, created_at, last_active, is_active) VALUES (?, ?, ?, ?, ?, ?)",
            (f"sess_{u_suffix}", u_id, f"jti_{u_suffix}", now, now, 1),
        )
        cursor.execute(
            "INSERT INTO analytics_events (event_id, user_id, event_type, entity_type, entity_id, properties, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"evt_{u_suffix}", u_id, "job.applied", "job", f"job_{u_suffix}", json.dumps({}), now),
        )
        cursor.execute(
            "INSERT INTO ab_experiments (experiment_id, user_id, name, variants, created_at) VALUES (?, ?, ?, ?, ?)",
            (f"exp_{u_suffix}", u_id, "Resume Variant Test", json.dumps(["A", "B"]), now),
        )
        cursor.execute(
            "INSERT INTO ab_assignments (assignment_id, experiment_id, user_id, entity_id, variant, assigned_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"asg_{u_suffix}", f"exp_{u_suffix}", u_id, f"job_{u_suffix}", "A", now),
        )
        cursor.execute(
            "INSERT INTO conversion_signals (signal_id, user_id, feature_type, feature_key, updated_at) VALUES (?, ?, ?, ?, ?)",
            (f"sig_{u_suffix}", u_id, "ATS", "Greenhouse", now),
        )

        # Seed User U in the 2 retained tables
        cursor.execute(
            "INSERT INTO security_audit_logs (log_id, user_id, event_type, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (f"log_{u_suffix}", u_id, "USER_LOGIN", json.dumps({"ip": "127.0.0.1"}), now),
        )
        cursor.execute(
            "INSERT INTO user_consents (consent_id, user_id, consent_type, version, consented, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"cns_{u_suffix}", u_id, "TERMS", "1.0", 1, now),
        )

        # Seed User V in multiple purged and retained tables to test no collateral deletion
        cursor.execute(
            "INSERT INTO users (user_id, email, password_hash, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (v_id, v_email, "hash_v", now, now),
        )
        cursor.execute(
            "INSERT INTO profiles (id, user_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (f"prof_{v_suffix}", v_id, json.dumps({"skills": ["Rust"]}), now),
        )
        cursor.execute(
            "INSERT INTO jobs (job_id, user_id, fingerprint, platform, company, title, location, url, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (f"job_{v_suffix}", v_id, f"fp_{v_suffix}", "Indeed", "DataCorp", "MLE", "Hybrid", "https://example.com/job2", "PENDING"),
        )
        cursor.execute(
            "INSERT INTO user_daily_usage (user_id, date, apply_count) VALUES (?, ?, ?)",
            (v_id, now_date, 3),
        )
        cursor.execute(
            "INSERT INTO analytics_events (event_id, user_id, event_type, entity_type, entity_id, properties, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (f"evt_{v_suffix}", v_id, "job.discovered", "job", f"job_{v_suffix}", json.dumps({}), now),
        )
        cursor.execute(
            "INSERT INTO security_audit_logs (log_id, user_id, event_type, details, created_at) VALUES (?, ?, ?, ?, ?)",
            (f"log_{v_suffix}", v_id, "USER_LOGIN", json.dumps({"ip": "127.0.0.1"}), now),
        )
        cursor.execute(
            "INSERT INTO user_consents (consent_id, user_id, consent_type, version, consented, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"cns_{v_suffix}", v_id, "TERMS", "1.0", 1, now),
        )
        cursor.execute(
            "INSERT INTO organizations (org_id, name, slug, owner_id, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (org_v_id, f"Org {v_suffix}", f"org-{v_suffix}", v_id, now, now),
        )
        cursor.execute(
            "INSERT INTO memberships (membership_id, org_id, user_id, role, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (f"mem_{v_suffix}", org_v_id, v_id, "OWNER", now, now),
        )
        conn.commit()

    try:
        # Execute Hard Erasure for User U
        result = db.hard_delete_user_account(u_id)
        assert result is True, "hard_delete_user_account should return True on success"

        with db.get_connection() as conn:
            cursor = conn.cursor()

            # 1. Assert all 20 user-scoped tables are completely purged for User U
            for table in PURGED_TABLES:
                col = "owner_id" if table == "organizations" else "user_id"
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} = ?", (u_id,))
                count = cursor.fetchone()[0]
                assert count == 0, f"Expected 0 rows for user {u_id} in {table}, found {count}"

            # 2. Assert retained compliance tables STILL retain User U's records (GDPR Art. 17(3))
            for table in RETAINED_TABLES:
                cursor.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id = ?", (u_id,))
                count = cursor.fetchone()[0]
                assert count > 0, f"Expected retained rows for user {u_id} in {table}, found {count}"

            # 3. Assert User V's data is 100% intact (zero collateral deletion)
            cursor.execute("SELECT COUNT(*) FROM users WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in users should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM profiles WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in profiles should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM jobs WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in jobs should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM user_daily_usage WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in user_daily_usage should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM analytics_events WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in analytics_events should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM security_audit_logs WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in security_audit_logs should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM user_consents WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in user_consents should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM organizations WHERE owner_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in organizations should remain untouched"

            cursor.execute("SELECT COUNT(*) FROM memberships WHERE user_id = ?", (v_id,))
            assert cursor.fetchone()[0] == 1, "User V in memberships should remain untouched"

    finally:
        # Idempotent cleanup for User V
        db.hard_delete_user_account(v_id)
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM security_audit_logs WHERE user_id = ?", (v_id,))
            cursor.execute("DELETE FROM user_consents WHERE user_id = ?", (v_id,))
            cursor.execute("DELETE FROM security_audit_logs WHERE user_id = ?", (u_id,))
            cursor.execute("DELETE FROM user_consents WHERE user_id = ?", (u_id,))
            conn.commit()
