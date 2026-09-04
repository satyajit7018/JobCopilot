"""
JobCopilot - Multi-Tenant Database Adapter Layer
Provides an abstract adapter interface supporting both local SQLite and Cloud PostgreSQL
with strict user/tenant isolation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from app.core.models import (
    User, CandidateProfile, VaultEntry, JobListing,
    HITLEvent, ApplicationStatus, OutreachRecord, EmailMessage, JobCheckpoint
)


class DatabaseAdapter(ABC):
    """Abstract interface for multi-tenant storage adapters."""

    @abstractmethod
    def create_user(self, user: User) -> bool:
        pass

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        pass

    @abstractmethod
    def save_profile(self, profile: CandidateProfile, user_id: str) -> bool:
        pass

    @abstractmethod
    def get_profile(self, user_id: str, profile_id: Optional[str] = None) -> Optional[CandidateProfile]:
        pass

    @abstractmethod
    def save_vault_entry(self, entry: VaultEntry, user_id: str) -> bool:
        pass

    @abstractmethod
    def get_vault_entries(self, user_id: str) -> List[VaultEntry]:
        pass

    @abstractmethod
    def save_job(self, job: JobListing, user_id: str) -> bool:
        pass

    @abstractmethod
    def get_jobs(self, user_id: str, status: Optional[ApplicationStatus] = None) -> List[JobListing]:
        pass

    @abstractmethod
    def get_job_by_id(self, job_id: str, user_id: str) -> Optional[JobListing]:
        pass

    @abstractmethod
    def save_hitl_event(self, event: HITLEvent, user_id: str) -> bool:
        pass

    @abstractmethod
    def get_pending_hitl(self, user_id: str) -> List[HITLEvent]:
        pass

    @abstractmethod
    def save_email(self, email: EmailMessage, user_id: str) -> bool:
        pass

    @abstractmethod
    def get_emails(self, user_id: str) -> List[EmailMessage]:
        pass

    @abstractmethod
    def save_outreach(self, record: OutreachRecord, user_id: str) -> bool:
        pass

    @abstractmethod
    def get_outreach(self, job_id: str, user_id: str) -> List[OutreachRecord]:
        pass

    @abstractmethod
    def get_funnel_metrics(self, user_id: str) -> Dict[str, Any]:
        pass

    # Apply Ledger Methods (with safe base defaults)
    def save_apply_ledger_entry(self, entry: Any, user_id: str) -> bool:
        return True

    def get_apply_ledger_entry(self, ledger_id: str, user_id: str) -> Optional[Any]:
        return None

    def get_active_ledger_by_fingerprint(self, fingerprint: str, user_id: str) -> Optional[Any]:
        return None

    def get_ledger_for_job(self, job_id: str, user_id: str) -> Optional[Any]:
        return None

    def list_user_apply_ledger(self, user_id: str, limit: int = 50, offset: int = 0, status: Optional[str] = None) -> List[Any]:
        return []


def get_db_adapter() -> DatabaseAdapter:
    """Factory function returning SQLite or PostgreSQL adapter based on DB_MODE."""
    from app.core.database import db
    return db
