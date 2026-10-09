"""Deleting an account deletes the person's files too (uploads, tailored resumes,
screenshots), and tailored resumes for different users never share a file."""

import asyncio
import uuid

from app.core.database import db
from app.core.models import CandidateProfile, User, UserRole
from app.core.resume_tailor import ResumeTailor
from app.core.settings import settings


def _user():
    u = User(user_id=f"usr_{uuid.uuid4().hex[:12]}", email=f"files_{uuid.uuid4().hex[:8]}@test.com",
             password_hash="x", role=UserRole.FREE, is_active=True)
    db.create_user(u)
    return u


def test_account_deletion_removes_user_files():
    user = _user()
    upload = settings.user_files_dir(user.user_id, "resumes") / "cv.pdf"
    upload.write_bytes(b"%PDF")
    shot = settings.user_files_dir(user.user_id, "screenshots") / "filled_job_1.png"
    shot.write_bytes(b"png")
    legacy = settings.resumes_dir / f"{user.user_id}_old.pdf"
    legacy.write_bytes(b"%PDF")
    other = settings.resumes_dir / "usr_someone_else_cv.pdf"
    other.write_bytes(b"%PDF")
    try:
        assert db.hard_delete_user_account(user.user_id)
        assert not upload.exists() and not shot.exists() and not legacy.exists()
        assert not (settings.app_dir / "users" / user.user_id).exists()
        assert other.exists(), "other people's files are untouched"
    finally:
        other.unlink(missing_ok=True)


def test_tailored_resumes_are_per_user(monkeypatch):
    async def fake_pdf(html, out_path):
        out_path.write_text(html)

    from app.core.resume_compiler import ResumeCompiler
    monkeypatch.setattr(ResumeCompiler, "compile_to_pdf", staticmethod(fake_pdf))
    a, b = _user(), _user()
    try:
        paths = []
        for u in (a, b):
            profile = CandidateProfile(id=u.user_id, user_id=u.user_id, full_name=u.user_id, email=u.email, phone="1",
                                       location="Pune", skills=["Python"])
            path, _, _ = asyncio.run(ResumeTailor.compile_tailored_resume_for_job(
                profile=profile, job_id="job_ab1234567890", job_title="Backend Engineer",
                job_description="Python", company_name="Acme"))
            paths.append(path)
        assert paths[0] != paths[1]
        assert a.user_id in str(paths[0]) and b.user_id in str(paths[1])
        assert a.user_id in paths[0].read_text()
    finally:
        db.hard_delete_user_account(a.user_id)
        db.hard_delete_user_account(b.user_id)
