"""
JobCopilot - Organization & Multi-Tenant Team Workspaces Router
Handles team workspaces, invitations, RBAC roles (OWNER, ADMIN, MEMBER),
and organization lifecycle management.
"""

import re
import uuid
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Depends, status

from app.core.database import db
from app.core.models import (
    User, Organization, Membership, OrgRole,
    CreateOrgRequest, UpdateOrgRequest, InviteMemberRequest, UpdateMemberRoleRequest,
    OrgResponse, MemberResponse
)
from app.api.auth import get_current_user, get_current_org_membership, require_org_admin, require_org_owner

router = APIRouter(prefix="/orgs", tags=["organizations"])


def _slugify(name: str) -> str:
    """Converts a human-readable organization name into a clean, URL-safe slug."""
    s = re.sub(r'[^\w\s-]', '', name.lower().strip())
    return re.sub(r'[-\s]+', '-', s)


@router.post("", response_model=OrgResponse, status_code=status.HTTP_201_CREATED)
async def create_organization(
    payload: CreateOrgRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Creates a new team organization.
    The creator is automatically granted the OWNER role.
    """
    clean_name = payload.name.strip()
    if not clean_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization name is required.")

    base_slug = payload.slug.strip().lower() if payload.slug else _slugify(clean_name)
    if not base_slug:
        base_slug = f"org-{uuid.uuid4().hex[:6]}"

    # Ensure slug uniqueness
    slug = base_slug
    existing = db.get_organization_by_slug(slug)
    if existing:
        slug = f"{base_slug}-{uuid.uuid4().hex[:4]}"

    org_id = f"org_{uuid.uuid4().hex[:12]}"
    new_org = Organization(
        org_id=org_id,
        name=clean_name,
        slug=slug,
        owner_id=current_user.user_id,
        plan_tier="FREE"
    )

    if not db.create_organization(new_org):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to create organization.")

    # Assign creator as OWNER in memberships
    membership = Membership(
        membership_id=f"mem_{uuid.uuid4().hex[:12]}",
        org_id=org_id,
        user_id=current_user.user_id,
        role=OrgRole.OWNER
    )
    db.add_membership(membership)

    return OrgResponse(
        org_id=new_org.org_id,
        name=new_org.name,
        slug=new_org.slug,
        owner_id=new_org.owner_id,
        plan_tier=new_org.plan_tier,
        created_at=new_org.created_at,
        role=OrgRole.OWNER.value
    )


@router.get("", response_model=List[OrgResponse])
async def list_user_organizations(current_user: User = Depends(get_current_user)):
    """Lists all organizations the authenticated user belongs to."""
    orgs = db.list_user_organizations(current_user.user_id)
    return [
        OrgResponse(
            org_id=o["org_id"],
            name=o["name"],
            slug=o["slug"],
            owner_id=o["owner_id"],
            plan_tier=o["plan_tier"],
            created_at=o["created_at"],
            role=o["role"]
        ) for o in orgs
    ]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_organization_details(
    org_id: str,
    current_user: User = Depends(get_current_user)
):
    """Gets details of an organization if the user is a member."""
    membership = await get_current_org_membership(org_id, current_user)
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    return OrgResponse(
        org_id=org.org_id,
        name=org.name,
        slug=org.slug,
        owner_id=org.owner_id,
        plan_tier=org.plan_tier,
        created_at=org.created_at,
        role=membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    )


@router.patch("/{org_id}", response_model=OrgResponse)
async def update_organization_settings(
    org_id: str,
    payload: UpdateOrgRequest,
    current_user: User = Depends(get_current_user)
):
    """Updates organization name or plan tier (requires OWNER or ADMIN)."""
    membership = await require_org_admin(org_id, current_user)
    org = db.get_organization(org_id)
    if not org:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found.")

    success = db.update_organization(org_id, name=payload.name, plan_tier=payload.plan_tier)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update organization.")

    updated_org = db.get_organization(org_id)
    return OrgResponse(
        org_id=updated_org.org_id,
        name=updated_org.name,
        slug=updated_org.slug,
        owner_id=updated_org.owner_id,
        plan_tier=updated_org.plan_tier,
        created_at=updated_org.created_at,
        role=membership.role.value if hasattr(membership.role, 'value') else str(membership.role)
    )


@router.get("/{org_id}/members", response_model=List[MemberResponse])
async def list_organization_members(
    org_id: str,
    current_user: User = Depends(get_current_user)
):
    """Lists all members of an organization (requires membership)."""
    _ = await get_current_org_membership(org_id, current_user)
    members = db.list_org_members(org_id)
    return [
        MemberResponse(
            membership_id=m["membership_id"],
            org_id=m["org_id"],
            user_id=m["user_id"],
            email=m["email"],
            full_name=m["full_name"],
            role=m["role"],
            created_at=m["created_at"]
        ) for m in members
    ]


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=status.HTTP_201_CREATED)
async def invite_organization_member(
    org_id: str,
    payload: InviteMemberRequest,
    current_user: User = Depends(get_current_user)
):
    """Invites a user to the organization by email (requires OWNER or ADMIN)."""
    _ = await require_org_admin(org_id, current_user)
    
    clean_email = payload.email.lower().strip()
    target_user = db.get_user_by_email(clean_email)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No registered user found with that email address.")

    existing_membership = db.get_membership(org_id, target_user.user_id)
    if existing_membership:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User is already a member of this organization.")

    new_mem = Membership(
        membership_id=f"mem_{uuid.uuid4().hex[:12]}",
        org_id=org_id,
        user_id=target_user.user_id,
        role=payload.role,
        invited_by=current_user.user_id
    )

    if not db.add_membership(new_mem):
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to add organization member.")

    return MemberResponse(
        membership_id=new_mem.membership_id,
        org_id=org_id,
        user_id=target_user.user_id,
        email=target_user.email,
        full_name=target_user.full_name,
        role=new_mem.role.value if hasattr(new_mem.role, 'value') else str(new_mem.role),
        created_at=new_mem.created_at
    )


@router.patch("/{org_id}/members/{user_id}")
async def update_organization_member_role(
    org_id: str,
    user_id: str,
    payload: UpdateMemberRoleRequest,
    current_user: User = Depends(get_current_user)
):
    """Updates a member's role (requires OWNER)."""
    _ = await require_org_owner(org_id, current_user)
    
    target_membership = db.get_membership(org_id, user_id)
    if not target_membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in organization.")

    if user_id == current_user.user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change your own role as owner.")

    role_val = payload.role.value if hasattr(payload.role, 'value') else str(payload.role)
    success = db.update_member_role(org_id, user_id, role_val)
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to update member role.")

    return {
        "status": "success",
        "org_id": org_id,
        "user_id": user_id,
        "new_role": role_val
    }


@router.delete("/{org_id}/members/{user_id}")
async def remove_organization_member(
    org_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user)
):
    """Removes a member from the organization or allows a member to leave."""
    membership = await get_current_org_membership(org_id, current_user)
    current_role = membership.role.value if hasattr(membership.role, 'value') else str(membership.role)

    # If leaving own membership
    if user_id == current_user.user_id:
        if current_role == "OWNER":
            members = db.list_org_members(org_id)
            if len(members) > 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Organization owner cannot leave while other members exist. Transfer ownership first."
                )
        success = db.remove_membership(org_id, user_id)
        return {"status": "success", "message": "Successfully left the organization."}

    # Removing someone else requires OWNER or ADMIN
    if current_role not in ["OWNER", "ADMIN"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin permissions required to remove members.")

    target_membership = db.get_membership(org_id, user_id)
    if not target_membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in organization.")

    target_role = target_membership.role.value if hasattr(target_membership.role, 'value') else str(target_membership.role)
    if target_role == "OWNER":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the organization owner.")
    if current_role == "ADMIN" and target_role == "ADMIN":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins cannot remove other admins. Contact the owner.")

    db.remove_membership(org_id, user_id)
    return {"status": "success", "message": "Member removed from organization."}
