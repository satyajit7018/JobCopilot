# 🔒 JobCopilot Privacy & Data Protection Policy

**Last Updated:** August 31, 2026  
**Version:** 1.0.0

At JobCopilot, we consider candidate privacy and personal data sovereignty to be core engineering requirements, not afterthoughts. This document outlines how JobCopilot processes, stores, encrypts, and isolates your candidate data.

---

## 1. Core Privacy Principles

1. **Local-First & Self-Hostable:** JobCopilot is designed to run entirely on your own infrastructure or local machine using SQLite Write-Ahead Logging (WAL) or your private PostgreSQL database.
2. **Transparent PII Encryption at Rest:** Highly sensitive candidate fields (phone number, expected compensation / CTC, current employer, physical location, recruiter talking points) are automatically encrypted using **AES-256-GCM** before being written to database storage.
3. **Zero Third-Party Ad Trackers or Telemetry Spies:** The JobCopilot frontend contains zero Google Analytics, Meta Pixels, or external ad scripts. Inbound recruiter emails are automatically scrubbed of 1x1 tracking pixels.
4. **Strict Tenant Boundary Enforcement:** Every database table and query enforces strict cryptographic ownership (`WHERE user_id = :user_id`) to ensure zero cross-tenant data leakage in multi-user deployments.

---

## 2. What Data We Process

| Data Category | Examples | Storage Location | Protection Level |
|:---|:---|:---|:---|
| **Identity & Authentication** | Email address, name, password hash | `users` table | Argon2id Hash (time_cost=3, memory_cost=64MB) |
| **Candidate PII** | Phone, current employer, expected CTC | `profiles.data` column | AES-256-GCM Envelope Encryption (`enc:...`) |
| **Resume & Documents** | Raw resume text, compiled PDF variants | Local Storage / S3 / R2 | Pre-signed URLs with 15-minute expiration |
| **Recruiter Communications** | Inbound emails, phone call logs | `emails`, `outreach_records` | Tenant-scoped database records |
| **Q&A Knowledge Vault** | Question embeddings, interview answers | `vault` table | Local vector embeddings with strict `user_id` scoping |

---

## 3. Cryptographic Key Management

- **Envelope Encryption:** Encryption keys are derived using PBKDF2 / Argon2id from `VAULT_MASTER_KEY` with a persistent salt.
- **Fail-Closed Secrets:** In `production` environments, the application strictly refuses to start if `VAULT_MASTER_KEY` or `JWT_SECRET` use default or low-entropy values (< 32 characters).
- **Single-Use Tokens:** Password reset tokens and refresh tokens are one-time use and immediately blacklisted in `revoked_tokens` upon rotation.

---

## 4. Inbound Email & Webhook Privacy

- **Subaddress Routing:** Inbound emails are attributed directly to your tenant ID using subaddress routing (e.g. `radar+usr_9f43ab@jobcopilot.app`).
- **Signature Verification:** External webhooks from Postmark, SendGrid, and Mailgun are validated using cryptographic HMAC-SHA256 signatures (`INBOUND_EMAIL_WEBHOOK_SECRET`).
- **Tracking Pixel Stripping:** Inbound recruiter HTML emails are sanitized with regex engines to neutralize known tracking beacons and tracking URLs.

---

## 5. Candidate Rights & Data Deletion

You retain 100% ownership of your resume assets and career history. To purge your account:
- All database records tied to your `user_id` across `users`, `profiles`, `vault`, `jobs`, `hitl_events`, and `emails` are permanently cascaded and erased.
- Generated PDF resumes in the object store are deleted.

For privacy questions or audits, contact: **privacy@jobcopilot.local**
