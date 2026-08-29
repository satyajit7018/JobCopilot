"""
JobCopilot - Milestone 8 Comprehensive Pytest Suite
Tests Disaster Recovery, AES-256-GCM Encrypted Backup, SHA-256 Integrity Verification,
and Database State Restoration.
"""

import sys
import os
import uuid
from pathlib import Path

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

import pytest
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.models import CandidateProfile, JobListing, ApplicationStatus
from app.core.database import DatabaseManager
from app.core.backup import BackupManager


class TestMilestone8:

    def test_backup_and_restore_cycle(self, tmp_path):
        # 1. Setup Source Database
        source_db_path = tmp_path / "source.db"
        source_db = DatabaseManager(source_db_path)

        profile = CandidateProfile(
            id="user_backup_test",
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            skills=["Python", "FastAPI", "Docker"]
        )
        source_db.save_profile(profile)

        job = JobListing(
            job_id="job_backup_1",
            fingerprint="fp_bk_1",
            platform="Greenhouse",
            company="Anthropic",
            title="AI Safety Engineer",
            url="https://boards.greenhouse.io/anthropic/1",
            status=ApplicationStatus.SUBMITTED
        )
        source_db.save_job(job)

        # 2. Export Encrypted Backup
        backup_file = tmp_path / "test_export.jobcopilot.enc"
        exported_path = BackupManager.export_encrypted_backup(
            output_file=backup_file,
            db_instance=source_db
        )
        assert exported_path.exists()
        assert exported_path.stat().st_size > 0

        # Verify content is encrypted (not plain JSON)
        with open(exported_path, "r") as f:
            raw_content = f.read()
            assert "Anthropic" not in raw_content
            assert "scorpionsatyajit" not in raw_content

        # 3. Restore into Target Database
        target_db_path = tmp_path / "target_restored.db"
        target_db = DatabaseManager(target_db_path)

        restore_res = BackupManager.restore_encrypted_backup(
            backup_file=exported_path,
            target_db=target_db
        )
        assert restore_res["status"] == "success"
        assert restore_res["restored_counts"]["profiles"] >= 1
        assert restore_res["restored_counts"]["jobs"] >= 1

        # 4. Verify Target DB content
        restored_profile = target_db.get_profile("user_backup_test")
        assert restored_profile is not None
        assert restored_profile.full_name == "Satyajit Nayak"

        restored_jobs = target_db.get_jobs()
        assert any(j.company == "Anthropic" for j in restored_jobs)

    def test_tamper_detection(self, tmp_path):
        source_db_path = tmp_path / "tamper_src.db"
        source_db = DatabaseManager(source_db_path)
        backup_file = tmp_path / "tamper.jobcopilot.enc"
        BackupManager.export_encrypted_backup(output_file=backup_file, db_instance=source_db)

        # Tamper with file
        with open(backup_file, "w") as f:
            f.write("corrupted_cipher_data_tampered")

        target_db = DatabaseManager(tmp_path / "tamper_target.db")
        with pytest.raises(Exception):
            BackupManager.restore_encrypted_backup(backup_file, target_db=target_db)

    @pytest.mark.asyncio
    async def test_backup_api_endpoints(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/backup/export")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "success"
            assert ".jobcopilot.enc" in data["filename"]
            assert Path(data["backup_path"]).exists()
