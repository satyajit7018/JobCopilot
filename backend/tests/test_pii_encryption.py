"""
JobCopilot - PII Encryption at Rest Test Suite
Validates that sensitive candidate PII (phone, expected_ctc, location, employer)
is encrypted with AES-256-GCM in the underlying database columns and roundtrips cleanly.
"""

import json
import uuid
import pytest
from app.core.database import db
from app.core.models import CandidateProfile, RecruiterPreferences, Project


def test_profile_pii_encrypted_at_rest():
    """Asserts that raw profiles.data column contains ciphertext and no plaintext PII."""
    user_id = f"usr_pii_{uuid.uuid4().hex[:6]}"
    phone = "+1-555-867-5309"
    location = "San Francisco, CA"
    expected_ctc = "$185,000 / year"
    employer = "Secret Tech Corp"
    
    profile = CandidateProfile(
        id=user_id,
        user_id=user_id,
        full_name="Jane Doe",
        email=f"{user_id}@jobcopilot.test",
        phone=phone,
        location=location,
        skills=["Python", "FastAPI", "Security"],
        preferences=RecruiterPreferences(
            expected_ctc=expected_ctc,
            current_employer=employer
        ),
        projects=[Project(name="SecurityEngine", description="Encryption test")]
    )

    # 1. Save profile
    assert db.save_profile(profile, user_id=user_id) is True

    # 2. Inspect raw SQL column
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        assert row is not None
        raw_json_str = row["data"]
        raw_data = json.loads(raw_json_str)

        # Assert envelope marker exists
        assert raw_data.get("_pii_encrypted") is True

        # Assert sensitive fields are encrypted (start with enc:)
        assert raw_data["phone"].startswith("enc:")
        assert phone not in raw_json_str
        assert raw_data["location"].startswith("enc:")
        assert location not in raw_json_str
        assert raw_data["preferences"]["expected_ctc"].startswith("enc:")
        assert expected_ctc not in raw_json_str
        assert raw_data["preferences"]["current_employer"].startswith("enc:")
        assert employer not in raw_json_str

    # 3. Read profile through application layer (transparent decryption)
    retrieved = db.get_profile(user_id=user_id)
    assert retrieved is not None
    assert retrieved.phone == phone
    assert retrieved.location == location
    assert retrieved.preferences.expected_ctc == expected_ctc
    assert retrieved.preferences.current_employer == employer


def test_legacy_plaintext_profile_backfill():
    """Asserts that migrate_plaintext_profiles safely encrypts legacy unencrypted profiles."""
    user_id = f"usr_legacy_{uuid.uuid4().hex[:6]}"
    phone = "+1-555-123-4567"
    location = "Austin, TX"
    
    legacy_data = {
        "id": user_id,
        "user_id": user_id,
        "full_name": "Legacy Candidate",
        "email": f"{user_id}@jobcopilot.test",
        "phone": phone,
        "location": location,
        "skills": ["Legacy"],
        "preferences": {"expected_ctc": "25 LPA"},
        "projects": [],
        "education": [],
        "experience": [],
        "updated_at": "2026-08-31T00:00:00"
    }

    # Insert raw plaintext row
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO profiles (id, user_id, data, updated_at) VALUES (?, ?, ?, ?)",
            (user_id, user_id, json.dumps(legacy_data), "2026-08-31T00:00:00")
        )
        conn.commit()

    # Backfill migration
    migrated_count = db.migrate_plaintext_profiles()
    assert migrated_count >= 1

    # Verify column is now encrypted
    with db.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM profiles WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        raw_data = json.loads(row["data"])
        assert raw_data.get("_pii_encrypted") is True
        assert raw_data["phone"].startswith("enc:")

    # Verify retrieval
    retrieved = db.get_profile(user_id=user_id)
    assert retrieved is not None
    assert retrieved.phone == phone
    assert retrieved.location == location
