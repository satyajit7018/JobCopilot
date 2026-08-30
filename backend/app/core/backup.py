"""
JobCopilot - Disaster Recovery & Encrypted Backup Engine
Exports full local profile, Knowledge Vault, and application pipeline into
tamper-proof AES-256-GCM encrypted archives (.jobcopilot.enc) with SHA-256 checksums.
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime

from app.core.config import DATA_DIR
from app.core.database import db, DatabaseManager
from app.core.credential_vault import CredentialVault


class BackupManager:
    """Manages encrypted disaster recovery exports and restoration."""

    @classmethod
    def export_encrypted_backup(
        cls,
        user_id: Optional[str] = None,
        output_file: Optional[Path] = None,
        db_instance: Optional[DatabaseManager] = None
    ) -> Path:
        """Dumps SQLite state for a user, computes SHA-256 integrity hash, and encrypts with AES-256-GCM."""
        target_db = db_instance or db
        export_path = output_file or (DATA_DIR / f"backup_{user_id or 'all'}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jobcopilot.enc")

        with target_db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Fetch user-scoped profiles
            if user_id:
                cursor.execute("SELECT * FROM profiles WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("SELECT * FROM profiles")
            profiles = [dict(r) for r in cursor.fetchall()]
            
            # Fetch vault
            if user_id:
                cursor.execute("SELECT * FROM vault WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("SELECT * FROM vault")
            vault_entries = [dict(r) for r in cursor.fetchall()]

            # Fetch jobs
            if user_id:
                cursor.execute("SELECT * FROM jobs WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("SELECT * FROM jobs")
            jobs = [dict(r) for r in cursor.fetchall()]

            # Fetch emails
            if user_id:
                cursor.execute("SELECT * FROM emails WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("SELECT * FROM emails")
            emails = [dict(r) for r in cursor.fetchall()]

            # Fetch outreach
            if user_id:
                cursor.execute("SELECT * FROM outreach_records WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("SELECT * FROM outreach_records")
            outreach = [dict(r) for r in cursor.fetchall()]

        payload = {
            "version": "1.0.0",
            "timestamp": datetime.now().isoformat(),
            "user_id": user_id,
            "profiles": profiles,
            "vault": vault_entries,
            "jobs": jobs,
            "emails": emails,
            "outreach": outreach
        }

        payload_bytes = json.dumps(payload, indent=2).encode('utf-8')
        checksum = hashlib.sha256(payload_bytes).hexdigest()

        envelope = {
            "checksum": checksum,
            "payload": payload
        }

        # Encrypt with local AES-256-GCM vault
        vault_tool = CredentialVault()
        encrypted_envelope = vault_tool.encrypt_data(envelope)

        export_path.parent.mkdir(parents=True, exist_ok=True)
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(encrypted_envelope, f, indent=2)

        return export_path

    @classmethod
    def restore_encrypted_backup_buffer(
        cls,
        encrypted_bytes: bytes,
        user_id: str,
        target_db: Optional[DatabaseManager] = None
    ) -> Dict[str, Any]:
        """Decrypts in-memory encrypted backup buffer and restores strictly for the tenant."""
        db_mgr = target_db or db
        encrypted_payload = json.loads(encrypted_bytes.decode('utf-8'))

        vault_tool = CredentialVault()
        envelope = vault_tool.decrypt_data(encrypted_payload)
        if not isinstance(envelope, dict) or "payload" not in envelope or "checksum" not in envelope:
            raise ValueError("Corrupted or invalid backup envelope structure.")

        payload = envelope["payload"]
        checksum = envelope["checksum"]

        # Verify SHA-256 integrity
        payload_bytes = json.dumps(payload, indent=2).encode('utf-8')
        computed_checksum = hashlib.sha256(payload_bytes).hexdigest()
        if computed_checksum != checksum:
            raise ValueError("Integrity checksum mismatch: Backup file has been tampered with or corrupted.")

        restored_counts = {
            "profiles": len(payload.get("profiles", [])),
            "vault_entries": len(payload.get("vault", [])),
            "jobs": len(payload.get("jobs", [])),
            "emails": len(payload.get("emails", [])),
            "outreach": len(payload.get("outreach", []))
        }

        with db_mgr.get_connection() as conn:
            cursor = conn.cursor()
            for p in payload.get("profiles", []):
                cursor.execute("""
                INSERT OR REPLACE INTO profiles (id, user_id, data, updated_at)
                VALUES (?, ?, ?, ?)
                """, (p["id"], user_id, p["data"], p["updated_at"]))

            for v in payload.get("vault", []):
                cursor.execute("""
                INSERT OR REPLACE INTO vault (qa_id, user_id, slot_type, slot_key, question_pattern, embedding, answer_template, dynamic_variables, usage_count, last_used_at, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (v["qa_id"], user_id, v["slot_type"], v["slot_key"], v["question_pattern"], v["embedding"], v["answer_template"], v["dynamic_variables"], v["usage_count"], v.get("last_used_at"), v.get("created_at") or datetime.now().isoformat()))

            for j in payload.get("jobs", []):
                cursor.execute("""
                INSERT OR REPLACE INTO jobs (
                    job_id, user_id, fingerprint, platform, company, title, location, url,
                    description, salary_range, seniority_level, posted_date,
                    match_score, priority_score, match_reasons, missing_skills, status,
                    applied_at, application_id, confirmation_screenshot_path, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    j["job_id"], user_id, j["fingerprint"], j["platform"], j["company"], j["title"], j["location"], j["url"],
                    j.get("description"), j.get("salary_range"), j.get("seniority_level"), j.get("posted_date"),
                    j.get("match_score", 0.0), j.get("priority_score", 0.0), j.get("match_reasons"), j.get("missing_skills"), j.get("status", "DISCOVERED"),
                    j.get("applied_at"), j.get("application_id"), j.get("confirmation_screenshot_path"), j.get("notes")
                ))
            conn.commit()

        return {
            "status": "success",
            "message": "Backup restored successfully for tenant.",
            "restored_records": restored_counts,
            "restored_counts": restored_counts
        }

    @classmethod
    def restore_encrypted_backup(
        cls,
        backup_file: Path,
        target_db: Optional[DatabaseManager] = None,
        user_id: str = "default"
    ) -> Dict[str, Any]:
        """Decrypts, validates SHA-256 checksum, and restores state strictly for tenant."""
        if not Path(backup_file).exists():
            raise FileNotFoundError(f"Backup file not found: {backup_file}")

        with open(backup_file, "rb") as f:
            encrypted_bytes = f.read()

        return cls.restore_encrypted_backup_buffer(
            encrypted_bytes=encrypted_bytes,
            user_id=user_id,
            target_db=target_db
        )
