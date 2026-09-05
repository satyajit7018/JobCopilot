# JobCopilot Data Processing Agreement (DPA)

**Effective Date:** September 1, 2026  
**Version:** 1.0  
**Compliance Standard:** GDPR Article 28, UK GDPR, CCPA/CPRA (Cal. Civ. Code § 1798.140)  

This Data Processing Agreement ("DPA") supplements the JobCopilot Terms of Service between JobCopilot ("Data Processor") and the User or Enterprise Customer ("Data Controller") regarding the processing of candidate personal data.

---

## 1. Definitions & Roles of the Parties

1. **"Personal Data"**, **"Data Subject"**, **"Processing"**, and **"Supervisory Authority"** have the meanings assigned under the EU General Data Protection Regulation (Regulation (EU) 2016/679 - "GDPR").
2. **Roles:**
   - **Data Controller:** The Candidate (or hiring enterprise customer managing applicant pipelines) determines the purposes and essential means of processing personal data.
   - **Data Processor:** JobCopilot processes candidate personal data strictly on documented instructions from the Data Controller to provide career co-pilot automation and analytics services.

---

## 2. Scope, Nature & Purpose of Processing

| Processing Dimension | Specification |
| :--- | :--- |
| **Categories of Data Subjects** | Job seekers, career applicants, hiring managers, interviewers, platform users |
| **Categories of Personal Data** | Full name, email, phone number, employment history, education, skills, resumes, portfolio URLs, application status, interview notes |
| **Special Categories of Data** | Not requested; candidates are discouraged from uploading sensitive data (health, racial, or biometric data) |
| **Nature of Operations** | Parsing, indexing, semantic vector generation, ATS form population, interview coaching, salary benchmark modeling |
| **Duration of Processing** | Term of the customer relationship plus audit retention periods or until candidate-initiated account erasure |

---

## 3. Subprocessors

1. **Authorized Subprocessors:** The Controller authorizes JobCopilot to engage the following third-party infrastructure and AI model providers:
   - **OpenAI LLC / Anthropic PBC / Google Vertex AI:** Model inference and semantic embedding generation (Zero Data Retention agreement in enterprise tiers).
   - **Stripe, Inc.:** Subscription payment processing and PCI-compliant invoicing.
   - **Amazon Web Services (AWS) / Google Cloud Platform (GCP):** Cloud infrastructure, encrypted database storage, and edge networking.
2. **Subprocessor Safeguards:** All subprocessors are vetted under contractual terms providing equivalent technical and organizational protections to those in this DPA.
3. **Notification of Changes:** JobCopilot shall provide at least thirty (30) days' advance notice of any planned subprocessor changes via security advisory or API release notes.

---

## 4. Technical and Organizational Security Measures (TOMs)

JobCopilot enforces rigorous Technical and Organizational Measures to safeguard personal data against accidental loss, destruction, alteration, or unauthorized disclosure:

1. **Encryption Standards:**
   - **At Rest:** AES-256 encryption applied to all database tables, disk volumes, and document storage vaults.
   - **In Transit:** TLS 1.3 enforced across all public REST API endpoints and internal microservices.
2. **Multi-Tenant Isolation:**
   - Database queries are partitioned by `user_id` and `organization_id` foreign keys.
   - Cross-tenant leakage is prevented via deterministic scoping and automated unit/integration test gates.
3. **Identity & Access Management:**
   - Role-Based Access Control (RBAC) enforcing Least Privilege principles.
   - Multi-Factor Authentication (MFA) mandated for internal administrator consoles.
   - Administrative impersonation is strictly audited (`admin_audit_logs`) and ephemeral.

---

## 5. Assistance with Data Subject Rights (GDPR Articles 15–22)

JobCopilot provides automated programmatic mechanisms enabling Controllers to fulfill Data Subject requests without human intervention:

- **Right of Access (Article 15) & Portability (Article 20):** Candidates can request an instant machine-readable JSON bundle containing all stored data via `POST /api/v1/account/export`.
- **Right to Rectification (Article 16):** Resumes, questionnaire answers, and vault entries can be modified at any time via `PUT /api/v1/profile` and `POST /api/v1/vault/learn`.
- **Right to Erasure (Article 17):** Candidates can execute irrevocable cryptographic account erasure via `DELETE /api/v1/account`.
- **Consent Management (Article 7):** Granular consent grant and withdrawal via `POST /api/v1/compliance/consent`.

---

## 6. Security Incident & Breach Notification SLA

1. **Incident Detection:** JobCopilot maintains automated anomaly detection and audit logging for security events.
2. **Notification SLA:** In the event of a confirmed Personal Data Breach affecting candidate records, JobCopilot shall notify affected Controllers without undue delay and, where feasible, within **seventy-two (72) hours** of becoming aware of the incident.
3. **Content of Notice:** The breach notification shall describe the nature of the breach, affected data categories, estimated number of data subjects, and recommended mitigation actions.

---

## 7. Return and Deletion of Personal Data

Upon termination of services or upon candidate request via the account deletion endpoint:
1. JobCopilot shall permanently delete all personal data from primary transactional storage within twenty-four (24) hours.
2. Backup archives containing snapshot data will be naturally rotated and overwritten in accordance with the Disaster Recovery Policy (maximum 30-day retention).
3. Compliance audit logs (such as proof of consent grant and erasure audit markers) are retained in pseudonymous format strictly for statutory compliance.
