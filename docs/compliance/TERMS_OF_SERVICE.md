# JobCopilot Terms of Service

**Effective Date:** September 1, 2026  
**Version:** 1.0  
**Classification:** Public Legal Document  

Welcome to **JobCopilot** ("Company", "Platform", "we", "us", or "our"). These Terms of Service ("Terms") constitute a legally binding agreement between JobCopilot and you ("User", "Candidate", or "Customer") governing your access to and use of the JobCopilot website, REST APIs, browser automation agent, and candidate copilot platform.

---

## 1. Acceptance of Terms & Eligibility

1. By registering an account, accessing our REST API, running the JobCopilot background agent, or consenting via our interactive consent gate, you signify your irrevocable acceptance of these Terms.
2. If you are accepting on behalf of an employer or organization, you represent and warrant that you possess full legal authority to bind that entity.
3. You must be at least 18 years of age or the age of legal majority in your jurisdiction to use JobCopilot.

---

## 2. User Accounts, Authentication & Multi-Tenancy

1. **Identity & Authentication:** Candidates must authenticate via email/password or authorized OAuth 2.0 Identity Providers (e.g., Google SSO). Candidates are strictly responsible for maintaining credential confidentiality.
2. **Multi-Tenant Isolation:** JobCopilot provides cryptographically isolated tenancy. Organizations and individual candidates access data segregated by strictly bounded tenant foreign keys and Row-Level Security (RLS) policies.
3. **Account Integrity:** You agree never to impersonate any individual or entity, forge email headers, or misrepresent employment history or qualifications.

---

## 3. Autonomous AI Co-Pilot & Automation Services

1. **Service Scope:** JobCopilot provides candidate career automation, including AI-driven resume tailoring, interview question generation, salary negotiation modeling, and automated application submissions to public Application Tracking Systems (ATS).
2. **Human-in-the-Loop (HITL) Safeguards:**
   - JobCopilot employs explicit HITL triggers. Critical actions—including irreversible application submissions, high-consequence questionnaires, and salary counter-proposals—require affirmative candidate review or consent.
   - Candidates retain ultimate editorial authority over every submitted resume and questionnaire answer.
3. **No Guarantee of Employment:** JobCopilot provides optimization and application automation tooling; we do NOT guarantee interview callbacks, job offers, or specific compensation outcomes. Hiring decisions rest entirely with prospective employers.

---

## 4. Subscriptions, Tier Quotas & Billing Policies

1. **Billing Tiers:** JobCopilot offers tiered subscription plans (Free, Pro, Enterprise). Features such as daily application bot throughput, tailored resume variants, and mock interview bandwidth are governed by tier quotas.
2. **Payment Processing:** All subscription billing is processed via PCI-DSS Level 1 certified payment gateways (Stripe, Inc.). We do not store raw credit card numbers or CVVs on JobCopilot servers.
3. **Cancellation & Refunds:** Subscriptions may be canceled at any time via the billing portal. Cancellations take effect at the conclusion of the current billing period. Fees paid are non-refundable except where required by applicable consumer law.

---

## 5. Acceptable Use & Ethical AI Policy

1. **Prohibited Conduct:** You agree NOT to:
   - Use JobCopilot to flood job boards with fraudulent, fictitious, or malicious applications.
   - Attempt credential stuffing, brute-forcing, or denial-of-service against third-party employer portals.
   - Reverse-engineer, decompile, or extract proprietary model weights or source code from JobCopilot.
   - Upload malicious payloads, weaponized PDF resumes, or prompt-injection exploits into parsing pipelines.
2. **Autonomous Bot Etiquette:** Our automation agents respect target ATS rate limits, robots.txt directives where applicable, and implement exponential backoff to avoid overloading employer infrastructure.

---

## 6. Intellectual Property & Candidate Data Ownership

1. **Candidate Data Ownership:** You retain 100% ownership of your resume, career history, vault documents, and personal questionnaire answers. JobCopilot claims no ownership over your candidate assets.
2. **Platform License:** You grant JobCopilot a limited, non-exclusive, worldwide license to process, parse, embed, and transmit your candidate materials solely for the purpose of delivering JobCopilot services.
3. **AI Training Restrictions:** Candidate career data is NOT used to train public foundation models without explicit, opt-in consent recorded via our Compliance API (`POST /api/v1/compliance/consent`).

---

## 7. Disclaimers & Limitation of Liability

1. **As-Is Provision:** JobCopilot is provided on an "AS IS" and "AS AVAILABLE" basis without warranties of any kind, whether express, statutory, or implied.
2. **Limitation of Liability:** To the maximum extent permitted by applicable law, JobCopilot shall not be liable for any indirect, incidental, special, consequential, or punitive damages, including loss of profits, career opportunities, or goodwill. In no event shall JobCopilot’s aggregate liability exceed the amounts paid by you in the twelve (12) months preceding the claim.

---

## 8. Governing Law, Dispute Resolution & Account Erasure

1. **Governing Law:** These Terms shall be governed by and construed in accordance with the laws of the State of Delaware, United States, without regard to conflict of law principles.
2. **GDPR / CCPA Self-Service Erasure:** Candidates may at any time request full cryptographic erasure of their personal account and associated telemetry via `DELETE /api/v1/account` or by contacting `privacy@jobcopilot.io`.
3. **Amendments:** We reserve the right to update these Terms. Material changes will be accompanied by an updated policy version and require re-consent via the platform interface.
