"""
JobCopilot - Multi-Tenant Database Adapter Layer
Provides an abstract adapter interface supporting both local SQLite and Cloud PostgreSQL
with strict user/tenant isolation.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from app.core.models import (
    User, CandidateProfile, VaultEntry, JobListing,
    HITLEvent, ApplicationStatus, OutreachRecord, EmailMessage, JobCheckpoint,
    Organization, Membership, AdminAuditLog
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

    # SaaS Organization & Membership Methods (with safe base defaults)
    def create_organization(self, org: Organization) -> bool:
        return True

    def get_organization(self, org_id: str) -> Optional[Organization]:
        return None

    def get_organization_by_slug(self, slug: str) -> Optional[Organization]:
        return None

    def list_user_organizations(self, user_id: str) -> List[Dict[str, Any]]:
        return []

    def update_organization(self, org_id: str, name: Optional[str] = None, plan_tier: Optional[str] = None) -> bool:
        return True

    def add_membership(self, membership: Membership) -> bool:
        return True

    def get_membership(self, org_id: str, user_id: str) -> Optional[Membership]:
        return None

    def list_org_members(self, org_id: str) -> List[Dict[str, Any]]:
        return []

    def remove_membership(self, org_id: str, user_id: str) -> bool:
        return True

    def update_member_role(self, org_id: str, user_id: str, role: str) -> bool:
        return True

    # Admin Panel & Audit Logging Methods
    def log_admin_action(self, log_entry: AdminAuditLog) -> bool:
        return True

    def list_admin_audit_logs(self, limit: int = 50, offset: int = 0) -> List[AdminAuditLog]:
        return []

    def list_all_users(self, limit: int = 50, offset: int = 0, search: Optional[str] = None) -> List[Dict[str, Any]]:
        return []

    def count_all_users(self, search: Optional[str] = None) -> int:
        return 0

    def list_all_organizations(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return []

    def count_all_organizations(self) -> int:
        return 0

    def get_admin_system_metrics(self) -> Dict[str, Any]:
        return {
            "total_users": 0,
            "total_jobs": 0,
            "total_applications": 0,
            "active_subscriptions": {"FREE": 0, "PRO": 0, "ELITE": 0, "ADMIN": 0},
            "total_organizations": 0
        }

    # GDPR Data Portability & Erasure
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        return {"user_id": user_id}

    def hard_delete_user_account(self, user_id: str) -> bool:
        return True

    # Idempotency Engine Operations
    def save_idempotency_record(self, record: Dict[str, Any]) -> bool:
        return True

    def get_idempotency_record(self, idempotency_key: str, user_id: str = "default") -> Optional[Dict[str, Any]]:
        return None

    def update_idempotency_record(self, idempotency_key: str, status: str, status_code: int, response_headers: Dict[str, Any], response_body: str) -> bool:
        return True

    def delete_idempotency_record(self, idempotency_key: str) -> bool:
        return True

    def cleanup_expired_idempotency_keys(self) -> int:
        return 0

    # --- Epic F: MFA / TOTP Storage ---
    def get_mfa_credentials(self, user_id: str) -> Optional[Dict[str, Any]]:
        return None

    def save_mfa_credentials(self, user_id: str, secret: str, backup_codes: List[Dict[str, Any]], is_enabled: bool) -> bool:
        return True

    def delete_mfa_credentials(self, user_id: str) -> bool:
        return True

    # --- Epic F: Session & Device Management ---
    def create_session(self, session: Dict[str, Any]) -> bool:
        return True

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        return None

    def list_user_sessions(self, user_id: str, active_only: bool = True) -> List[Dict[str, Any]]:
        return []

    def revoke_session(self, session_id: str, user_id: str) -> bool:
        return True

    def revoke_all_user_sessions(self, user_id: str, except_jti: Optional[str] = None) -> int:
        return 0

    def update_session_activity(self, token_jti: str) -> bool:
        return True

    # --- Epic F: Security Audit Logs ---
    def insert_security_audit_log(self, log_entry: Dict[str, Any]) -> bool:
        return True

    def list_security_audit_logs(self, user_id: Optional[str] = None, event_type: Optional[str] = None, severity: Optional[str] = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        return []

    def count_security_audit_logs(self, user_id: Optional[str] = None, event_type: Optional[str] = None, severity: Optional[str] = None) -> int:
        return 0


def get_db_adapter() -> DatabaseAdapter:
    """Factory function returning SQLite or PostgreSQL adapter based on DB_MODE."""
    from app.core.database import db
    return db

