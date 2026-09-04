"""
JobCopilot - Idempotent Application Ledger & Audit Tracker
Provides atomic lock acquisition, state transitions, and double-apply prevention
for autonomous job application pipelines.
"""

import uuid
from datetime import datetime
from typing import Optional, Tuple, List

from app.core.models import ApplyLedgerEntry, ApplyLedgerStatus
from app.core.database import db


class ApplyLedgerManager:
    """Manages application idempotency locks and state transitions."""

    @classmethod
    def acquire_lock(
        cls,
        user_id: str,
        job_id: str,
        job_fingerprint: str,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3
    ) -> Tuple[bool, Optional[ApplyLedgerEntry], str]:
        """
        Atomically checks if an application attempt is allowed.
        Returns:
            (is_acquired: bool, entry: Optional[ApplyLedgerEntry], reason: str)
        """
        existing = db.get_active_ledger_by_fingerprint(job_fingerprint, user_id=user_id)
        if not existing:
            existing = db.get_ledger_for_job(job_id, user_id=user_id)

        now_str = datetime.now().isoformat()

        if existing:
            if existing.status == ApplyLedgerStatus.SUBMITTED:
                return False, existing, f"Application already submitted on {existing.updated_at}."
            if existing.status == ApplyLedgerStatus.IN_PROGRESS:
                return False, existing, "Application is currently actively executing."
            if existing.status == ApplyLedgerStatus.HITL_PAUSED:
                return False, existing, "Application is currently held for Human-In-The-Loop review."

            # If FAILED, check if under max retries
            if existing.status == ApplyLedgerStatus.FAILED:
                if existing.attempt_count >= existing.max_retries:
                    return False, existing, f"Application exceeded max retries ({existing.max_retries}). Last error: {existing.last_error_category}."
                
                # Re-acquire lock for next attempt
                existing.attempt_count += 1
                existing.status = ApplyLedgerStatus.INITIATED
                existing.updated_at = now_str
                db.save_apply_ledger_entry(existing, user_id=user_id)
                return True, existing, f"Retry lock acquired (Attempt {existing.attempt_count}/{existing.max_retries})."

        # Create brand new ledger entry
        new_id = f"ledger_{uuid.uuid4().hex[:12]}"
        entry = ApplyLedgerEntry(
            ledger_id=new_id,
            user_id=user_id,
            job_id=job_id,
            job_fingerprint=job_fingerprint,
            status=ApplyLedgerStatus.INITIATED,
            attempt_count=1,
            max_retries=max_retries,
            idempotency_key=idempotency_key or f"idem_{uuid.uuid4().hex[:8]}",
            created_at=now_str,
            updated_at=now_str
        )
        db.save_apply_ledger_entry(entry, user_id=user_id)
        return True, entry, "Application lock successfully acquired."

    @classmethod
    def mark_in_progress(cls, ledger_id: str, user_id: str) -> bool:
        """Transitions ledger state to IN_PROGRESS."""
        entry = db.get_apply_ledger_entry(ledger_id, user_id=user_id)
        if not entry:
            return False
        entry.status = ApplyLedgerStatus.IN_PROGRESS
        entry.updated_at = datetime.now().isoformat()
        return db.save_apply_ledger_entry(entry, user_id=user_id)

    @classmethod
    def mark_submitted(
        cls,
        ledger_id: str,
        user_id: str,
        confirmation_id: Optional[str] = None,
        screenshot_path: Optional[str] = None
    ) -> bool:
        """Transitions ledger state to SUBMITTED."""
        entry = db.get_apply_ledger_entry(ledger_id, user_id=user_id)
        if not entry:
            return False
        entry.status = ApplyLedgerStatus.SUBMITTED
        entry.confirmation_id = confirmation_id or entry.confirmation_id
        entry.screenshot_path = screenshot_path or entry.screenshot_path
        entry.updated_at = datetime.now().isoformat()
        return db.save_apply_ledger_entry(entry, user_id=user_id)

    @classmethod
    def mark_failed(
        cls,
        ledger_id: str,
        user_id: str,
        error_category: str,
        error_message: str
    ) -> bool:
        """Transitions ledger state to FAILED."""
        entry = db.get_apply_ledger_entry(ledger_id, user_id=user_id)
        if not entry:
            return False
        entry.status = ApplyLedgerStatus.FAILED
        entry.last_error_category = error_category
        entry.last_error_message = error_message
        entry.updated_at = datetime.now().isoformat()
        return db.save_apply_ledger_entry(entry, user_id=user_id)

    @classmethod
    def mark_hitl_paused(cls, ledger_id: str, user_id: str) -> bool:
        """Transitions ledger state to HITL_PAUSED pending user resolution."""
        entry = db.get_apply_ledger_entry(ledger_id, user_id=user_id)
        if not entry:
            return False
        entry.status = ApplyLedgerStatus.HITL_PAUSED
        entry.updated_at = datetime.now().isoformat()
        return db.save_apply_ledger_entry(entry, user_id=user_id)

    @classmethod
    def is_already_applied(cls, user_id: str, job_fingerprint: str) -> bool:
        """Quickly checks if a job has already been submitted by user."""
        existing = db.get_active_ledger_by_fingerprint(job_fingerprint, user_id=user_id)
        return bool(existing and existing.status == ApplyLedgerStatus.SUBMITTED)

    @classmethod
    def get_ledger_for_job(cls, user_id: str, job_id: str) -> Optional[ApplyLedgerEntry]:
        """Retrieves ledger entry for a specific job."""
        return db.get_ledger_for_job(job_id, user_id=user_id)

    @classmethod
    def list_user_ledger(
        cls,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[ApplyLedgerEntry]:
        """Retrieves paginated audit history of applications for a tenant."""
        return db.list_user_apply_ledger(user_id=user_id, limit=limit, offset=offset, status=status)


apply_ledger = ApplyLedgerManager()
