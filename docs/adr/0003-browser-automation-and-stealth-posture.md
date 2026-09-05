# 3. Browser Automation, Human Simulation, and Ethical Stealth Posture

Date: 2026-09-06

## Status

Accepted

## Context

JobCopilot automates repetitive job application form-filling across diverse Applicant Tracking Systems (ATS) like Greenhouse, Lever, Workday, and Ashby. Autonomous browser interactions on external company career portals face stringent anti-bot detection systems (Cloudflare Turnstile, reCAPTCHA, Datadome, Akamai).

Unethical bot behavior (brute-forcing CAPTCHAs, spamming submissions at inhuman rates, forging credentials) violates platform terms of service, burns candidate IP reputations, and triggers legal and compliance liabilities.

## Decision

We instituted an **Ethical Stealth and Human-in-the-Loop (HITL) Automation Posture**:
1. **Never Bypass CAPTCHAs**: Under no circumstances does JobCopilot attempt to solve or bypass CAPTCHAs algorithmically. Upon detecting a CAPTCHA challenge or high-entropy verification gate, the bot suspends execution, captures a screenshot, creates a `HITLEvent`, and notifies the candidate for manual intervention.
2. **Human Behavioral Simulation**:
   - Keystroke timing incorporates natural Gaussian jitter (50ms - 150ms per character).
   - Mouse trajectories utilize Bézier curves with realistic acceleration and deceleration curves rather than instantaneous coordinate teleportation.
   - Micro-delays between field transitions replicate human visual review behavior.
3. **Submission Idempotency**:
   - Every submission is recorded in `ApplyLedger` with a state machine (`PENDING -> SUBMITTING -> SUBMITTED | HELD | FAILED`).
   - Retries verify the ledger to prevent accidental duplicate applications to the same job.
4. **Transparent Identity**: Submissions are performed exclusively using the candidate's authentic credentials, résumés, and contact information with explicit candidate authorization.

## Consequences

### Positive
- Zero risk of legal liability associated with automated bypass mechanisms.
- Extremely low ban and rejection rates on ATS portals due to authentic human interaction dynamics.
- Complete auditability through screenshot evidence and ledger records.

### Negative / Trade-offs
- The bot cannot achieve 100% unattended automation on portals with active CAPTCHA challenges; user collaboration via HITL is strictly required.
