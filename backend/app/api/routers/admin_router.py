"""
JobCopilot - Admin Panel & System Oversight Router
Provides secure administrative operations: user and organization directories,
system-wide usage metrics, role elevation, and audit-logged impersonation.
"""

import uuid
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Request, status

from app.core.database import db
from app.core.models import (
    User, UserRole, AdminAuditLog,
    AdminUserListResponse, AdminOrgListResponse, AdminStatsResponse, AdminImpersonateResponse
)
from app.api.auth import require_admin, create_jwt_token, ACCESS_TOKEN_EXPIRE_MINUTES

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/users", response_model=AdminUserListResponse)
async def list_admin_users(
    limit: int = 50,
    offset: int = 0,
    search: Optional[str] = None,
    admin_user: User = Depends(require_admin)
):
    """Lists all registered users with optional search filter."""
    users = db.list_all_users(limit=limit, offset=offset, search=search)
    total = db.count_all_users(search=search)
    return AdminUserListResponse(
        users=users,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/orgs", response_model=AdminOrgListResponse)
async def list_admin_organizations(
    limit: int = 50,
    offset: int = 0,
    admin_user: User = Depends(require_admin)
):
    """Lists all organizations with member counts and plan tiers."""
    orgs = db.list_all_organizations(limit=limit, offset=offset)
    total = db.count_all_organizations()
    return AdminOrgListResponse(
        orgs=orgs,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/metrics", response_model=AdminStatsResponse)
async def get_admin_metrics(admin_user: User = Depends(require_admin)):
    """Returns platform-wide metrics: user count, job count, application count, tier breakdown."""
    metrics = db.get_admin_system_metrics()
    return AdminStatsResponse(**metrics)


@router.post("/impersonate/{user_id}", response_model=AdminImpersonateResponse)
async def impersonate_user(
    user_id: str,
    request: Request,
    admin_user: User = Depends(require_admin)
):
    """
    Issues an audit-logged, short-lived JWT access token allowing an admin to impersonate a tenant.
    All actions performed under this token contain an explicit 'impersonated_by' audit claim.
    """
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found.")

    client_ip = request.client.host if request.client else "unknown"
    role_str = target_user.role.value if hasattr(target_user.role, 'value') else str(target_user.role)

    # 1. Log impersonation event to admin audit log
    audit_entry = AdminAuditLog(
        log_id=f"audit_{uuid.uuid4().hex[:12]}",
        admin_id=admin_user.user_id,
        action="USER_IMPERSONATION",
        target_user_id=target_user.user_id,
        ip_address=client_ip,
        details={
            "admin_email": admin_user.email,
            "target_email": target_user.email,
            "reason": "Administrative support / diagnostics"
        }
    )
    db.log_admin_action(audit_entry)

    # 2. Issue scoped access token with impersonation claim
    token_claims = {
        "sub": target_user.user_id,
        "email": target_user.email,
        "role": role_str,
        "type": "access",
        "impersonated_by": admin_user.user_id
    }
    impersonation_token = create_jwt_token(
        token_claims,
        expires_delta=timedelta(minutes=15)  # Strict 15-minute window for impersonation
    )

    return AdminImpersonateResponse(
        access_token=impersonation_token,
        impersonated_user_id=target_user.user_id,
        impersonated_email=target_user.email,
        admin_id=admin_user.user_id,
        token_type="bearer"
    )


@router.get("/audit-logs")
async def get_admin_audit_logs(
    limit: int = 50,
    offset: int = 0,
    admin_user: User = Depends(require_admin)
):
    """Retrieves paginated admin audit trail."""
    logs = db.list_admin_audit_logs(limit=limit, offset=offset)
    return {
        "status": "success",
        "logs": [log.dict() for log in logs],
        "limit": limit,
        "offset": offset
    }


@router.get("/security-audit-logs")
async def get_system_security_audit_logs(
    user_id: Optional[str] = None,
    event_type: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    admin_user: User = Depends(require_admin)
):
    """Retrieves system-wide security audit logs and anomaly alerts (Admin only)."""
    from app.core.security_logger import security_logger
    return security_logger.get_logs(
        user_id=user_id,
        event_type=event_type,
        severity=severity,
        limit=limit,
        offset=offset
    )


@router.patch("/users/{user_id}/role")
async def update_user_role(
    user_id: str,
    role: str,
    request: Request,
    admin_user: User = Depends(require_admin)
):
    """Updates a user's subscription or system role."""
    target_user = db.get_user_by_id(user_id)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    valid_roles = ["FREE", "PRO", "ELITE", "ADMIN"]
    clean_role = role.upper().strip()
    if clean_role not in valid_roles:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid role. Must be one of {valid_roles}")

    success = db.update_user_role(user_id, clean_role)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update role.")

    # Log role change in admin audit logs
    client_ip = request.client.host if request.client else "unknown"
    audit_entry = AdminAuditLog(
        log_id=f"audit_{uuid.uuid4().hex[:12]}",
        admin_id=admin_user.user_id,
        action="UPDATE_USER_ROLE",
        target_user_id=user_id,
        ip_address=client_ip,
        details={
            "old_role": target_user.role.value if hasattr(target_user.role, 'value') else str(target_user.role),
            "new_role": clean_role
        }
    )
    db.log_admin_action(audit_entry)

    return {
        "status": "success",
        "user_id": user_id,
        "new_role": clean_role
    }
