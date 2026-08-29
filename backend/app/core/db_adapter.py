"""
JobCopilot - Multi-Tenant Database Adapter Layer
Provides an abstract adapter interface supporting both local SQLite and Cloud PostgreSQL
with Row-Level Security (RLS) and connection pooling.
"""

import os
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from pathlib import Path
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
    def save_profile(self, profile: CandidateProfile, user_id: str = "default") -> bool:
        pass

    @abstractmethod
    def get_profile(self, profile_id: str = "default_user", user_id: str = "default") -> Optional[CandidateProfile]:
        pass

    @abstractmethod
    def save_vault_entry(self, entry: VaultEntry, user_id: str = "default") -> bool:
        pass

    @abstractmethod
    def get_vault_entries(self, user_id: str = "default") -> List[VaultEntry]:
        pass

    @abstractmethod
    def save_job(self, job: JobListing, user_id: str = "default") -> bool:
        pass

    @abstractmethod
    def get_jobs(self, status: Optional[ApplicationStatus] = None, user_id: str = "default") -> List[JobListing]:
        pass

    @abstractmethod
    def get_job_by_id(self, job_id: str, user_id: str = "default") -> Optional[JobListing]:
        pass

    @abstractmethod
    def save_hitl_event(self, event: HITLEvent, user_id: str = "default") -> bool:
        pass

    @abstractmethod
    def get_pending_hitl(self, user_id: str = "default") -> List[HITLEvent]:
        pass

    @abstractmethod
    def save_email(self, email: EmailMessage, user_id: str = "default") -> bool:
        pass

    @abstractmethod
    def get_emails(self, user_id: str = "default") -> List[EmailMessage]:
        pass

    @abstractmethod
    def save_outreach(self, record: OutreachRecord, user_id: str = "default") -> bool:
        pass

    @abstractmethod
    def get_outreach(self, job_id: str, user_id: str = "default") -> List[OutreachRecord]:
        pass

    @abstractmethod
    def get_funnel_metrics(self, user_id: str = "default") -> Dict[str, Any]:
        pass


def get_db_adapter() -> DatabaseAdapter:
    """Factory function returning SQLite or PostgreSQL adapter based on DB_MODE."""
    from app.core.database import db
    return db
