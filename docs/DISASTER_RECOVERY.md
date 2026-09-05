# JobCopilot Disaster Recovery (DR) Charter & Runbook

## 1. Executive Charter & Objectives

| Objective | Target SLA | Metric Definition |
| :--- | :--- | :--- |
| **Recovery Point Objective (RPO)** | **≤ 15 Minutes** | Maximum allowable data loss measured in time between last persistent backup/WAL and disaster event. |
| **Recovery Time Objective (RTO)** | **≤ 1 Hour** | Maximum allowable elapsed time from incident declaration to verified operational recovery in secondary site. |
| **Data Integrity Level** | **100%** | Zero tolerance for unverified corruption; SHA-256 cryptographic checksums verified before and after restore. |
| **Drill Frequency** | **Automated Monthly / Quarterly Manual** | Synthetic drill simulation script runs regularly in CI and staging. |

---

## 2. Backup Topology & Architecture

### 2.1 Database Backups (PostgreSQL & SQLite WAL)
1. **Continuous Write-Ahead Log (WAL) Archival**:
   - For PostgreSQL: AWS RDS automated continuous backups with point-in-time recovery (PITR) up to 14 days, streaming WAL records to multi-region S3 with 5-minute sync intervals.
   - For SQLite (Edge/Local installations): Online atomic snapshot via SQLite backup API (`vacuum into` / `.backup`) guaranteeing 0 table locks during execution.
2. **Scheduled Full Backups**:
   - Hourly incremental diffs and daily full snapshots created by `scripts/dr_backup.py`.
   - Backups are encrypted with envelope encryption and stored with S3 Object Lock (WORM - Write Once, Read Many) to prevent ransomware tampering.
3. **Multi-Region Cross-Replication**:
   - Primary Region: `us-east-1`
   - Secondary Region: `us-west-2` (cross-region replication with KMS customer-managed key).

---

## 3. Disaster Scenarios & Recovery Runbooks

### Scenario A: RDS Instance or Node Failure (Automatic Failover)
- **Detection**: RDS health check fails or AWS AZ outage alert.
- **Action**: Multi-AZ RDS automatically promotes the standby replica in the secondary AZ within 60–120 seconds.
- **Client Impact**: Applications experience ~1 minute of connection retries; circuit breakers prevent cascading failures.
- **Recovery Time**: ~2 minutes (well within 1-hour RTO).

### Scenario B: Accidental Table Deletion or Logical Data Corruption
- **Detection**: Application error alerts or support escalation.
- **Action**: Execute Point-in-Time Recovery (PITR) to timestamp $T_{incident} - 2\text{ minutes}$.
  ```bash
  aws rds restore-db-instance-to-point-in-time \
    --source-db-instance-identifier jobcopilot-db-production \
    --target-db-instance-identifier jobcopilot-db-restored \
    --restore-time 2026-09-06T00:00:00Z
  ```
- **Validation**: Run `scripts/dr_restore_drill.py` to verify data consistency before swapping DNS.

### Scenario C: Region-Wide Cloud Outage
- **Detection**: Primary AWS region unavailable for > 15 minutes.
- **Action**:
  1. Trigger Terraform failover deployment in secondary region:
     ```bash
     cd infra/terraform && terraform apply -var="aws_region=us-west-2"
     ```
  2. Restore database from cross-region replicated snapshot using `scripts/dr_restore_drill.py`.
  3. Update Route53 DNS records to point to secondary Ingress gateway.
- **Expected RTO**: 35–45 minutes.

---

## 4. Disaster Recovery Drill Simulator

Run the automated DR drill script to simulate a complete failure and restore:
```bash
PYTHONPATH=backend python scripts/dr_restore_drill.py
```
The script verifies:
1. Snapshot creation and SHA-256 hash sealing.
2. Complete restore into an isolated sandbox environment.
3. Schema parity, user count, and application ledger verification.
4. Calculation and confirmation that execution completes within the RTO SLA.
