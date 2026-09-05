# 2. Multi-Tenant Organization and User Isolation Architecture

Date: 2026-09-06

## Status

Accepted

## Context

JobCopilot processes sensitive personal identifying information (PII), job applications, compensation benchmarks, executive recruiter notes, and OAuth tokens. As teams and enterprise organizations adopt the platform, data isolation cannot rely on developer discipline or client-side filtering. Inadvertent cross-tenant data leaks represent a fatal compliance and security risk.

## Decision

We enforced a **Cryptographic and Schema-Enforced Multi-Tenant Isolation Architecture**:
1. **Tenant Identification**: Every user session is resolved into a verified `user_id` and optional `org_id` via signed JWT Bearer tokens with server-side revocation validation (`revoked_tokens` blacklist table).
2. **Default-Deny Dependency**: All authenticated routes inherit from `Depends(get_current_user)` or `Depends(get_current_org_member)`, preventing any unauthenticated entrypoint from accessing tenant resources.
3. **Database-Level Row Isolation**: Every database query on sensitive entities (`jobs`, `profiles`, `vault`, `analytics_events`, `ab_experiments`, `conversion_signals`, `audit_logs`) includes an explicit tenant constraint:
   - `WHERE user_id = ?` (or `WHERE org_id = ?`).
   - Cross-tenant queries are structurally impossible because IDs are always scoped by the authenticated caller's identity rather than caller-supplied URL parameters.
4. **Envelope Cryptography for Sensitive Data**: High-sensitivity PII and credentials stored in the `CredentialVault` are encrypted at rest using AES-256-GCM.
5. **Role-Based Access Control (RBAC)**: Within organizations, roles are strictly partitioned into `OWNER`, `ADMIN`, and `MEMBER`, validated via `verify_org_role` security dependency.

## Consequences

### Positive
- Strict tenant boundary verified by dedicated automated tests (`test_security_tenant_isolation.py`, `test_discovery_tenancy.py`).
- Clear audit trail with `AdminAuditLog` recording all organizational administrative operations.

### Negative / Trade-offs
- Every data access method must accept and enforce `user_id` or `org_id`.
- Global administrative operations require explicit, audited impersonation protocols (`/api/v1/admin/impersonate`).
