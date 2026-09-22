"""
JobCopilot - Idempotent Application Ledger & Audit Tracker
Provides atomic lock acquisition, state transitions, and double-apply prevention
for autonomous job application pipelines.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple

from app.core.database import db
from app.core.models import ApplyLedgerEntry, ApplyLedgerStatus


class ApplyLedgerManager:
    """Manages application idempotency locks and state transitions."""

    STALE_INITIATED_AFTER = timedelta(minutes=10)

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
            status = existing.status.value if hasattr(existing.status, "value") else str(existing.status)
            if status == ApplyLedgerStatus.SUBMITTED.value:
                return False, existing, f"Application already submitted on {existing.updated_at}."
            if status == ApplyLedgerStatus.IN_PROGRESS.value:
                return False, existing, "Application is currently actively executing."
            if status == ApplyLedgerStatus.HITL_PAUSED.value:
                return False, existing, "Application is currently held for Human-In-The-Loop review."

            if status == ApplyLedgerStatus.INITIATED.value:
                # Queued but never started. Reclaim only if it has been stuck long enough that the
                # original dispatch clearly died (it never reached IN_PROGRESS, so nothing was submitted).
                stale_before = (datetime.now() - cls.STALE_INITIATED_AFTER).isoformat()
                if db.transition_ledger_status(existing.ledger_id, user_id, [ApplyLedgerStatus.INITIATED.value],
                                               ApplyLedgerStatus.INITIATED.value, older_than_iso=stale_before):
                    return True, db.get_apply_ledger_entry(existing.ledger_id, user_id=user_id), "Reclaimed a stale queued application."
                return False, existing, "Application is already queued."

            if status == ApplyLedgerStatus.CANCELLED.value:
                # Released by a dry run or a user cancel: nothing was submitted, safe to start again.
                if db.transition_ledger_status(existing.ledger_id, user_id, [ApplyLedgerStatus.CANCELLED.value],
                                               ApplyLedgerStatus.INITIATED.value):
                    return True, db.get_apply_ledger_entry(existing.ledger_id, user_id=user_id), "Application lock acquired."
                return False, db.get_apply_ledger_entry(existing.ledger_id, user_id=user_id), "Application is already queued."

            if status == ApplyLedgerStatus.FAILED.value:
                if existing.attempt_count >= existing.max_retries:
                    return False, existing, f"Application exceeded max retries ({existing.max_retries}). Last error: {existing.last_error_category}."
                # Atomic FAILED -> INITIATED: exactly one concurrent retry can win (audit P0-4 race).
                if db.transition_ledger_status(existing.ledger_id, user_id, [ApplyLedgerStatus.FAILED.value],
                                               ApplyLedgerStatus.INITIATED.value, increment_attempt=True):
                    fresh = db.get_apply_ledger_entry(existing.ledger_id, user_id=user_id)
                    return True, fresh, f"Retry lock acquired (Attempt {fresh.attempt_count}/{fresh.max_retries})."
                return False, db.get_apply_ledger_entry(existing.ledger_id, user_id=user_id), "Another retry already acquired this application."

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
        if db.insert_ledger_if_absent(entry, user_id=user_id):
            return True, entry, "Application lock successfully acquired."

        # A concurrent request already inserted; re-read and return conflict
        existing_or_none = db.get_ledger_for_job(job_id, user_id=user_id) or db.get_active_ledger_by_fingerprint(job_fingerprint, user_id=user_id)
        return False, existing_or_none, "Application is currently actively executing."

    @classmethod
    def mark_in_progress(cls, ledger_id: str, user_id: str) -> bool:
        """Atomic INITIATED -> IN_PROGRESS. Only one runner can ever start a given attempt."""
        return db.transition_ledger_status(ledger_id, user_id, [ApplyLedgerStatus.INITIATED.value],
                                           ApplyLedgerStatus.IN_PROGRESS.value)

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
    def release_after_dry_run(cls, ledger_id: str, user_id: str) -> bool:
        """A dry run never submits, so it must not hold the lock or look SUBMITTED (audit P1-3)."""
        return db.transition_ledger_status(ledger_id, user_id, [ApplyLedgerStatus.IN_PROGRESS.value],
                                           ApplyLedgerStatus.CANCELLED.value)

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
