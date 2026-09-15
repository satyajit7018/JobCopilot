"""
JobCopilot - GDPR Object Storage Purge Test
Verifies that ObjectStorageAdapter.purge_user permanently deletes local storage
for the specified user without impacting other tenants or failing on edge cases.
"""

from app.core.object_storage import ObjectStorageAdapter


def test_gdpr_storage_purge_local(tmp_path):
    storage = ObjectStorageAdapter(backend="local")
    storage.local_base_dir = tmp_path

    user_u = "usr_gdpr_u_storage_test"
    user_v = "usr_gdpr_v_storage_test"

    # Upload files for User U
    resume_u_path = storage.upload_resume(user_u, "resume.pdf", b"%PDF-1.4 User U Resume")
    screenshot_u_path = storage.upload_screenshot(user_u, "job_abc", b"PNG User U Screenshot")
    assert resume_u_path
    assert screenshot_u_path

    # Upload files for User V
    resume_v_path = storage.upload_resume(user_v, "resume.pdf", b"%PDF-1.4 User V Resume")
    assert resume_v_path

    u_dir = tmp_path / "users" / user_u
    v_dir = tmp_path / "users" / user_v

    assert u_dir.exists() and u_dir.is_dir(), f"User U storage dir should exist at {u_dir}"
    assert v_dir.exists() and v_dir.is_dir(), f"User V storage dir should exist at {v_dir}"

    # Guard tests: empty or invalid user_id must return False and delete nothing
    assert storage.purge_user("") is False
    assert storage.purge_user("   ") is False
    assert storage.purge_user(None) is False  # type: ignore

    # Verify both U and V directories are untouched after failed guard calls
    assert u_dir.exists()
    assert v_dir.exists()

    # Purge User U
    purge_result = storage.purge_user(user_u)
    assert purge_result is True, "purge_user should return True on successful purge"

    # Assert User U's directory is completely gone
    assert not u_dir.exists(), "User U storage directory should be deleted"

    # Assert User V's directory and files are 100% intact (no collateral deletion)
    assert v_dir.exists() and v_dir.is_dir(), "User V storage directory must remain intact"
    v_resume = v_dir / "resumes" / "resume.pdf"
    assert v_resume.exists(), "User V resume must remain intact"
    assert v_resume.read_bytes() == b"%PDF-1.4 User V Resume"

    # Idempotence: purging an already non-existent user should succeed safely
    assert storage.purge_user(user_u) is True
