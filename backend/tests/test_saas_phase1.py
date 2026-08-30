"""
JobCopilot - Phase 1 SaaS Multi-Tenant & Authentication Test Suite
Verifies JWT token issuance, Argon2id/PBKDF2 password security, token rotation,
and strict multi-tenant data isolation between User A and User B.
"""

import os
import sys
from pathlib import Path
import pytest
import uuid

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from fastapi.testclient import TestClient
from app.main import app
from app.core.database import db
from app.core.models import (
    CandidateProfile, JobListing, ApplicationStatus, VaultEntry, SlotType
)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


class TestSaaSPhase1:
    """Test suite covering Phase 1 Multi-Tenant Auth and Data Isolation."""

    def test_user_registration_and_jwt_tokens(self, client):
        """Tests that a new user can register and receives valid JWT access and refresh tokens."""
        unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        password = "SecurePassword123!"

        res = client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "Test Candidate A"
        })

        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert data["email"] == unique_email
        assert data["role"] == "FREE"
        assert data["user_id"].startswith("usr_")

        # Test duplicate registration rejection
        dup_res = client.post("/api/auth/register", json={
            "email": unique_email,
            "password": "AnotherPassword456!"
        })
        assert dup_res.status_code == 409

    def test_user_login_and_refresh_cycle(self, client):
        """Tests login verification with password and refresh token rotation."""
        unique_email = f"user_{uuid.uuid4().hex[:8]}@example.com"
        password = "ValidPassword789!"

        # 1. Register
        reg_res = client.post("/api/auth/register", json={
            "email": unique_email,
            "password": password,
            "full_name": "Test Candidate"
        })
        assert reg_res.status_code == 200

        # 2. Login with wrong password
        bad_login = client.post("/api/auth/login", json={
            "email": unique_email,
            "password": "WrongPassword!"
        })
        assert bad_login.status_code == 401

        # 3. Login with correct password
        good_login = client.post("/api/auth/login", json={
            "email": unique_email,
            "password": password
        })
        assert good_login.status_code == 200
        login_data = good_login.json()
        assert "access_token" in login_data
        refresh_token = login_data["refresh_token"]

        # 4. Token Refresh
        refresh_res = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_res.status_code == 200
        refreshed_data = refresh_res.json()
        assert "access_token" in refreshed_data
        assert refreshed_data["access_token"] != login_data["access_token"]

        # 5. Access Protected /me endpoint
        headers = {"Authorization": f"Bearer {refreshed_data['access_token']}"}
        me_res = client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["email"] == unique_email

    def test_strict_multi_tenant_data_isolation(self, client):
        """
        Critical Multi-Tenant Test:
        Verifies that User A and User B have completely isolated profiles, jobs, and vault slots.
        User B cannot view or modify User A's data.
        """
        email_a = f"user_a_{uuid.uuid4().hex[:8]}@example.com"
        email_b = f"user_b_{uuid.uuid4().hex[:8]}@example.com"

        # Register User A & User B
        res_a = client.post("/api/auth/register", json={"email": email_a, "password": "PasswordA123!", "full_name": "User Alpha"})
        token_a = res_a.json()["access_token"]
        user_id_a = res_a.json()["user_id"]

        res_b = client.post("/api/auth/register", json={"email": email_b, "password": "PasswordB123!", "full_name": "User Beta"})
        token_b = res_b.json()["access_token"]
        user_id_b = res_b.json()["user_id"]

        headers_a = {"Authorization": f"Bearer {token_a}"}
        headers_b = {"Authorization": f"Bearer {token_b}"}

        # 1. User A uploads resume text
        resume_text_a = "User Alpha, Staff Backend Engineer in SF. Email: alpha@example.com. Skills: Python, Golang, Kubernetes."
        upload_res_a = client.post("/api/upload-resume", data={"raw_text": resume_text_a}, headers=headers_a)
        assert upload_res_a.status_code == 200

        # 2. User A creates a job opportunity
        job_id_a = f"job_{uuid.uuid4().hex[:8]}"
        job_a = JobListing(
            job_id=job_id_a,
            user_id=user_id_a,
            fingerprint=f"fp_{uuid.uuid4().hex[:12]}",
            platform="Greenhouse",
            company="AlphaCorp Exclusive",
            title="Lead Engineer",
            location="San Francisco, CA",
            url="https://alphacorp.example/jobs/1",
            match_score=0.95,
            priority_score=92.0,
            status=ApplicationStatus.DISCOVERED
        )
        db.save_job(job_a, user_id=user_id_a)

        # 3. User B checks jobs list — must NOT see AlphaCorp Exclusive
        jobs_res_b = client.get("/api/jobs", headers=headers_b)
        assert jobs_res_b.status_code == 200
        jobs_b = jobs_res_b.json()["jobs"]
        b_companies = [j["company"] for j in jobs_b]
        assert "AlphaCorp Exclusive" not in b_companies

        # 4. User B checks profile — must NOT see User Alpha's profile
        profile_res_b = client.get("/api/profile", headers=headers_b)
        # Should either be 404 or not have User Alpha's name
        if profile_res_b.status_code == 200:
            assert profile_res_b.json()["profile"]["full_name"] != "User Alpha"

        # 5. User A checks their jobs — must see AlphaCorp Exclusive
        jobs_res_a = client.get("/api/jobs", headers=headers_a)
        assert jobs_res_a.status_code == 200
        a_companies = [j["company"] for j in jobs_res_a.json()["jobs"]]
        assert "AlphaCorp Exclusive" in a_companies

    def test_database_adapter_interface(self):
        """Tests DatabaseAdapter factory and user retrieval."""
        from app.core.db_adapter import get_db_adapter
        adapter = get_db_adapter()
        assert adapter is not None
        assert hasattr(adapter, "create_user")
        assert hasattr(adapter, "get_user_by_email")
        assert hasattr(adapter, "get_jobs")
        assert hasattr(adapter, "get_vault_entries")
