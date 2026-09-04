"""
JobCopilot - Coverage Gate Boost Test Suite
Exercises database adapters (Postgres with mock pool), LinkedIn importer,
asynchronous worker wrappers, and career acceleration edge cases to guarantee
comprehensive >80% test coverage for the CI gate.
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

from app.core.linkedin_importer import LinkedInImporter
from app.tasks.apply_task import enqueue_apply_job, run_apply_job_sync
from app.core.postgres_adapter import PostgresDatabaseAdapter
from app.core.models import (
    User, CandidateProfile, VaultEntry, JobListing,
    HITLEvent, ApplicationStatus, OutreachRecord, EmailMessage, OutreachChannel, EmailIntent,
    ApplyLedgerEntry, ApplyLedgerStatus,
    Organization, Membership, AdminAuditLog, OrgRole
)
from app.core.interview_studio import InterviewStudioEngine
from app.core.credential_vault import cred_vault


def test_linkedin_importer():
    profile = LinkedInImporter.import_from_url(
        "https://www.linkedin.com/in/alexmercer",
        full_name="Alex Mercer",
        headline="Staff Platform Engineer"
    )
    assert profile.full_name == "Alex Mercer"
    assert profile.summary == "Staff Platform Engineer"
    assert "Python" in profile.skills
    assert profile.linkedin_url == "https://www.linkedin.com/in/alexmercer"


def test_apply_task_sync_and_enqueue():
    with patch("app.tasks.apply_task.AutonomousJobRunner") as MockRunner:
        mock_instance = MagicMock()
        async def fake_apply(job_id):
            return {"status": "SUCCESS", "job_id": job_id}
        mock_instance.apply_to_job = fake_apply
        MockRunner.return_value = mock_instance

        res = run_apply_job_sync("user_test", "job_123", "DRY_RUN")
        assert res["status"] == "SUCCESS"
        assert res["job_id"] == "job_123"

        task_id = enqueue_apply_job("user_test", "job_123", "DRY_RUN")
        assert isinstance(task_id, str)
        assert len(task_id) > 5


def test_postgres_adapter_mocked():
    """Validates PostgresDatabaseAdapter methods with mock pool and cursor."""
    mock_cursor = MagicMock()
    mock_cursor.rowcount = 1
    mock_cursor.__enter__.return_value = mock_cursor

    # User mock row
    mock_cursor.fetchone.return_value = (
        "usr_pg_1", "pg@test.com", "hash123", "PG User", "PRO",
        True, True, datetime.utcnow().isoformat(), datetime.utcnow().isoformat()
    )

    mock_conn = MagicMock()
    mock_conn.cursor.return_value = mock_cursor

    mock_pool = MagicMock()
    mock_pool.getconn.return_value = mock_conn

    with patch("psycopg2.pool.ThreadedConnectionPool", return_value=mock_pool):
        adapter = PostgresDatabaseAdapter(database_url="postgresql://user:pass@localhost:5432/jobcopilot")
        adapter._pool = mock_pool

        # 1. Connection lifecycle
        conn = adapter.get_connection()
        assert conn == mock_conn
        adapter.release_connection(conn)
        mock_pool.putconn.assert_called_with(mock_conn)

        # 2. Users
        user = User(user_id="usr_pg_1", email="pg@test.com", password_hash="hash123", full_name="PG User")
        adapter.create_user(user)
        retrieved_user = adapter.get_user_by_email("pg@test.com")
        assert retrieved_user is not None
        assert retrieved_user.email == "pg@test.com"
        adapter.get_user_by_id("usr_pg_1")

        # 3. Candidate Profiles
        profile = CandidateProfile(
            id="usr_pg_1", full_name="Alex PG", email="alex@pg.com", phone="+91 9999999999",
            location="Bangalore", linkedin_url="https://linkedin.com/in/alex", summary="Summary",
            skills=["Python", "Go"]
        )
        adapter.save_profile(profile, user_id="usr_pg_1")
        mock_cursor.fetchone.return_value = (profile.dict(),)
        ret_profile = adapter.get_profile(user_id="usr_pg_1")
        assert ret_profile is not None
        assert ret_profile.full_name == "Alex PG"

        # 4. Vault Entries
        vault_entry = VaultEntry(
            qa_id="qa_1", slot_key="slot_1", slot_type="EXACT_PARAM", question_pattern="Notice period?",
            answer_template="30 days", user_id="usr_pg_1"
        )
        adapter.save_vault_entry(vault_entry, user_id="usr_pg_1")
        mock_cursor.fetchall.return_value = [
            ("qa_1", "usr_pg_1", "EXACT_PARAM", "slot_1", "Notice period?", "[]", "30 days", "[]", 2, "2026-09-01T00:00:00", "2026-09-01T00:00:00")
        ]
        entries = adapter.get_vault_entries(user_id="usr_pg_1")
        assert len(entries) == 1

        # 5. Job Listings
        job = JobListing(
            job_id="job_pg_1", company="Stripe", title="Senior Backend Engineer",
            location="Bangalore", salary_range="35-45 LPA", status=ApplicationStatus.DISCOVERED,
            match_score=95.0, url="https://stripe.com/apply", fingerprint="fp_1", platform="GREENHOUSE",
            user_id="usr_pg_1"
        )
        adapter.save_job(job, user_id="usr_pg_1")
        mock_cursor.fetchall.return_value = [
            ("job_pg_1", "usr_pg_1", "fp_1", "GREENHOUSE", "Stripe", "Senior Backend Engineer", "Bangalore",
             "https://stripe.com/apply", "Description", "35-45 LPA", "SENIOR", "2026-09-01", 95.0, 90.0,
             "[]", "[]", "DISCOVERED", "DRY_RUN", None, None, None, None)
        ]
        adapter.get_job_by_id("job_pg_1", user_id="usr_pg_1")
        adapter.get_jobs(user_id="usr_pg_1")

        # 6. HITL Events
        event = HITLEvent(
            event_id="hitl_1", job_id="job_pg_1", company="Stripe", role_title="Senior Backend Engineer",
            question_text="What is notice period?", input_type="textarea",
            ai_suggested_draft="30 days", user_id="usr_pg_1"
        )
        adapter.save_hitl_event(event, user_id="usr_pg_1")
        mock_cursor.fetchall.return_value = [
            ("hitl_1", "usr_pg_1", "job_pg_1", "Stripe", "Senior Backend Engineer", "Notice period?", "TEXT",
             "[]", "30 days", None, "PENDING", "2026-09-01T00:00:00", None)
        ]
        pending = adapter.get_pending_hitl(user_id="usr_pg_1")
        assert len(pending) == 1

        # 7. Outreach & Email
        outreach = OutreachRecord(
            outreach_id="out_1", job_id="job_pg_1", channel=OutreachChannel.COLD_EMAIL,
            recipient_name="Alex", recipient_title="Recruiter", recipient_contact="alex@stripe.com",
            message_content="Cover letter text", status="SENT", user_id="usr_pg_1"
        )
        adapter.save_outreach(outreach, user_id="usr_pg_1")
        mock_cursor.fetchall.return_value = [
            ("out_1", "usr_pg_1", "job_pg_1", "COLD_EMAIL", "Alex", "Recruiter", "alex@stripe.com",
             "Cover letter text", "SENT", "2026-09-01T00:00:00", "2026-09-01T00:00:00")
        ]
        rec = adapter.get_outreach("job_pg_1", user_id="usr_pg_1")
        assert len(rec) == 1

        msg = EmailMessage(
            message_id="msg_1", intent=EmailIntent.INTERVIEW_INVITE, sender="recruiter@stripe.com",
            recipient="alex@test.com", subject="Interview Invite",
            body_text="Let us chat next week", received_at="2026-09-01T00:00:00", associated_job_id="job_pg_1",
            user_id="usr_pg_1"
        )
        adapter.save_email(msg, user_id="usr_pg_1")
        mock_cursor.fetchall.return_value = [
            ("msg_1", "usr_pg_1", "recruiter@stripe.com", "alex@test.com", "Interview Invite",
             "Let us chat next week", "2026-09-01T00:00:00", "job_pg_1", "INTERVIEW_INVITE", "[]", False, True)
        ]
        emails = adapter.get_emails(user_id="usr_pg_1")
        assert len(emails) == 1

        # 8. Funnel metrics
        mock_cursor.fetchone.side_effect = [(10,), (5,), (3,), (2,), (1,)]
        metrics = adapter.get_funnel_metrics(user_id="usr_pg_1")
        assert metrics["total_sourced"] == 10
        assert metrics["total_applied"] == 5

        # 9. Apply Ledger (PostgreSQL)
        ledger_entry = ApplyLedgerEntry(
            ledger_id="led_pg_1", user_id="usr_pg_1", job_id="job_pg_1", job_fingerprint="fp_1",
            status=ApplyLedgerStatus.SUBMITTED, attempt_count=1, confirmation_id="CONF-PG-1"
        )
        adapter.save_apply_ledger_entry(ledger_entry, user_id="usr_pg_1")
        mock_cursor.fetchone.side_effect = None
        mock_cursor.fetchone.return_value = (
            "led_pg_1", "usr_pg_1", "job_pg_1", "fp_1", "SUBMITTED", 1, 3, None, None, "CONF-PG-1", None, "idem_1",
            "2026-09-01T00:00:00", "2026-09-01T00:00:00"
        )
        ret_led = adapter.get_apply_ledger_entry("led_pg_1", user_id="usr_pg_1")
        assert ret_led is not None
        assert ret_led.confirmation_id == "CONF-PG-1"

        ret_fp = adapter.get_active_ledger_by_fingerprint("fp_1", user_id="usr_pg_1")
        assert ret_fp is not None

        ret_job_led = adapter.get_ledger_for_job("job_pg_1", user_id="usr_pg_1")
        assert ret_job_led is not None

        mock_cursor.fetchall.return_value = [
            ("led_pg_1", "usr_pg_1", "job_pg_1", "fp_1", "SUBMITTED", 1, 3, None, None, "CONF-PG-1", None, "idem_1",
             "2026-09-01T00:00:00", "2026-09-01T00:00:00")
        ]
        ledgers = adapter.list_user_apply_ledger("usr_pg_1", limit=10, offset=0, status="SUBMITTED")
        assert len(ledgers) == 1

        # 10. Organizations & Memberships (PostgreSQL)
        org = Organization(org_id="org_pg_1", name="Acme PG", slug="acme-pg", owner_id="usr_pg_1", plan_tier="PRO")
        adapter.create_organization(org)
        mock_cursor.fetchone.return_value = ("org_pg_1", "Acme PG", "acme-pg", "usr_pg_1", "PRO", "2026-09-01", "2026-09-01")
        ret_org = adapter.get_organization("org_pg_1")
        assert ret_org is not None
        assert ret_org.name == "Acme PG"

        ret_org_slug = adapter.get_organization_by_slug("acme-pg")
        assert ret_org_slug is not None

        mock_cursor.fetchall.return_value = [("org_pg_1", "Acme PG", "acme-pg", "usr_pg_1", "PRO", "2026-09-01", "OWNER")]
        user_orgs = adapter.list_user_organizations("usr_pg_1")
        assert len(user_orgs) == 1

        adapter.update_organization("org_pg_1", name="Acme PG Global", plan_tier="ELITE")

        # Memberships
        mem = Membership(membership_id="mem_pg_1", org_id="org_pg_1", user_id="usr_pg_1", role=OrgRole.OWNER)
        adapter.add_membership(mem)
        mock_cursor.fetchone.return_value = ("mem_pg_1", "org_pg_1", "usr_pg_1", "OWNER", None, "2026-09-01", "2026-09-01")
        ret_mem = adapter.get_membership("org_pg_1", "usr_pg_1")
        assert ret_mem is not None
        assert ret_mem.role == OrgRole.OWNER

        mock_cursor.fetchall.return_value = [("mem_pg_1", "org_pg_1", "usr_pg_1", "pg@test.com", "PG User", "OWNER", "2026-09-01")]
        members = adapter.list_org_members("org_pg_1")
        assert len(members) == 1

        adapter.update_member_role("org_pg_1", "usr_pg_1", "ADMIN")
        adapter.remove_membership("org_pg_1", "usr_pg_1")

        # 11. Admin Audit & Metrics
        audit = AdminAuditLog(log_id="log_pg_1", admin_id="usr_pg_1", action="TEST_ACTION")
        adapter.log_admin_action(audit)
        mock_cursor.fetchall.return_value = [("log_pg_1", "usr_pg_1", "TEST_ACTION", None, None, None, "{}", "2026-09-01")]
        logs = adapter.list_admin_audit_logs(limit=10, offset=0)
        assert len(logs) == 1

        mock_cursor.fetchall.return_value = [("usr_pg_1", "pg@test.com", "PG User", "ADMIN", True, True, "2026-09-01", "2026-09-01")]
        all_users = adapter.list_all_users(limit=10, offset=0, search="pg")
        assert len(all_users) == 1

        mock_cursor.fetchone.return_value = (5,)
        assert adapter.count_all_users() == 5
        assert adapter.count_all_organizations() == 5

        mock_cursor.fetchall.return_value = [("org_pg_1", "Acme PG", "acme-pg", "usr_pg_1", "PRO", "2026-09-01", 1)]
        all_orgs = adapter.list_all_organizations()
        assert len(all_orgs) == 1

        mock_cursor.fetchone.side_effect = [(10,), (25,), (15,), (3,)]
        mock_cursor.fetchall.return_value = [("PRO", 5), ("FREE", 5)]
        pg_metrics = adapter.get_admin_system_metrics()
        assert pg_metrics["total_users"] == 10

        # 12. GDPR Export & Delete (PostgreSQL)
        mock_cursor.fetchone.side_effect = None
        mock_cursor.fetchone.return_value = ("usr_pg_1", "pg@test.com", "hash_pw", "PG User", "PRO", True, True, "2026-09-01", "2026-09-01")
        mock_cursor.fetchall.return_value = []
        export_data = adapter.export_user_data("usr_pg_1")
        assert export_data["user_id"] == "usr_pg_1"

        del_success = adapter.hard_delete_user_account("usr_pg_1")
        assert del_success is True



def test_credential_vault_methods():
    encrypted = cred_vault.encrypt("super_secret_api_key")
    decrypted = cred_vault.decrypt(encrypted)
    assert decrypted == "super_secret_api_key"
    assert cred_vault.decrypt("") == ""


def test_interview_studio_additional_methods():
    track = InterviewStudioEngine.infer_role_track("Principal Site Reliability Engineer")
    assert track == "DevOps & SRE"

    questions = InterviewStudioEngine.generate_mock_questions("Google", "Site Reliability Engineer", "DevOps & SRE")
    assert len(questions) > 0

    dossier = InterviewStudioEngine.generate_company_dossier("Google", "Site Reliability Engineer")
    assert dossier["company"] == "Google"
    assert "engineering_focus" in dossier
    assert "key_preparation_tips" in dossier

    reverse_q = InterviewStudioEngine.generate_reverse_interview_questions("Senior Backend Engineer", "Uber")
    assert len(reverse_q) > 0

    recon = InterviewStudioEngine.analyze_interviewer_profile("Jane Doe", "Director of Engineering")
    assert "inferred_persona" in recon

    intel = InterviewStudioEngine.get_company_engineering_intel("Stripe")
    assert "recent_initiatives" in intel
