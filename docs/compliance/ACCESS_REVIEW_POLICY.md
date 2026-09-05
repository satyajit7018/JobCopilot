# JobCopilot Access Review & User Privilege Policy

**Effective Date:** September 1, 2026  
**Version:** 1.0  
**Compliance Standard:** SOC 2 CC6.1, CC6.2, CC6.3; ISO/IEC 27001:2022 A.9.2  
**Classification:** Internal Operational Policy & Compliance Requirement  

---

## 1. Purpose & Scope

This policy establishes mandatory operational requirements for granting, modifying, periodically auditing, and revoking logical access to JobCopilot production infrastructure, databases, API gateways, third-party vendor platforms, and customer tenant environments.

This policy applies to all JobCopilot employees, contractors, service accounts, automated CI/CD runners, and enterprise organization administrators.

---

## 2. Core Access Principles

1. **Principle of Least Privilege (PoLP):** Users and service accounts are granted only the minimum access levels strictly necessary to perform authorized business tasks.
2. **Need-to-Know Basis:** Access to sensitive candidate personal data (PII, resumes, offer details) is restricted to automated processing pipelines; human access requires explicit approval and auditing.
3. **Segregation of Duties:** Development and production environments are strictly separated. Developers do not possess default write access to production database clusters.
4. **Mandatory Multi-Factor Authentication (MFA):** MFA is enforced on all identity providers, GitHub organizations, cloud consoles (AWS/GCP), and production management endpoints.

---

## 3. User Roles & Access Hierarchies

### 3.1 System-Level Roles (`UserRole`)

| Role | Permissions & Scope | Approval Authority | Review Cadence |
| :--- | :--- | :--- | :--- |
| **SUPERADMIN** | Root infrastructure access, system configuration, global metrics, emergency interventions | CTO / CISO | Monthly |
| **ADMIN** | User directory management, organization oversight, audit log inspection, customer support impersonation | Engineering Director | Quarterly |
| **RECRUITER** | Candidate pipeline management, interview scheduling, ATS synchronization | Tenant Organization Admin | Continuous |
| **CANDIDATE** | Self-service application bot, profile editing, vault management, personal consent controls | Self (Automated Registration) | Continuous |

### 3.2 Multi-Tenant Organization Roles (`OrgRole`)

| Role | Permissions & Scope |
| :--- | :--- |
| **OWNER** | Full organizational control, billing management, subscription upgrades, member invitations, deletion |
| **ADMIN** | Member invitations, role adjustments, shared template management, analytics review |
| **MEMBER** | Access to shared application boards, resume variant templates, and team telemetry |

---

## 4. Periodic Access Review Cadence

JobCopilot mandates formal access audits conducted on the following recurring schedules:

| Target System / Tier | Frequency | Responsible Reviewer | Evidentiary Artifact |
| :--- | :--- | :--- | :--- |
| **Cloud Infrastructure (AWS/GCP IAM)** | Quarterly | Security Officer / DevOps Lead | IAM Access Analyzer Report & Signed Audit Sign-off |
| **Production Database Access** | Monthly | Lead Database Administrator | Connection logs and Active User Role Listing |
| **Third-Party API Credentials (Stripe, OpenAI)** | Monthly | Engineering Director | Secret rotation log and token usage audit |
| **Customer Tenant Administrators** | Continuous / In-App | Enterprise Organization Owner | `GET /api/v1/orgs/{org_id}/members` review |

---

## 5. Administrative Impersonation Governance

When JobCopilot engineers require temporary access to troubleshoot candidate accounts, strict controls apply:

1. **Explicit Justification:** The administrator must supply an affirmative ticket ID or customer support justification.
2. **Ephemeral Token Lifetime:** Impersonation tokens are issued with a strict 15-minute expiration window (`ACCESS_TOKEN_EXPIRE_MINUTES`).
3. **Mandatory Immutable Audit Log:** Every impersonation session writes an entry to `admin_audit_logs` capturing:
   - `admin_user_id`
   - `target_user_id`
   - `action` (`IMPERSONATE_USER`)
   - `reason` / ticket reference
   - Client IP address and timestamp
4. **Financial Action Prohibition:** Impersonated sessions are cryptographically barred from initiating financial transactions or altering payment credentials.

---

## 6. Access Revocation & Offboarding SLA

1. **Immediate Revocation (Involuntary Termination):** Access to all code repositories, cloud consoles, communication channels, and VPN credentials must be terminated within **one (1) hour** of employee departure notification.
2. **Scheduled Revocation (Voluntary Termination):** Access is scheduled to expire automatically at the close of the employee's final working day.
3. **Candidate Account Self-Erasure:** When a candidate triggers `DELETE /api/v1/account`, all active JWT sessions are immediately invalidated, and database records are permanently purged.

---

## 7. Audit Logging & Compliance Evidentiary Retention

Records of completed quarterly access reviews, including signed reviewer sign-offs, identified privilege creep remediations, and credential rotation logs, are preserved for a minimum of **three (3) years** to support SOC 2 and ISO 27001 external audits.
