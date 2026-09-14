"""
JobCopilot - Disaster Recovery restore drill (P1-2).
Continuously proves the backup -> restore -> integrity pipeline actually works,
instead of leaving dr_restore_drill.py as an unexercised standalone script.
"""

from scripts.dr_restore_drill import run_dr_restore_drill


def test_dr_restore_drill_succeeds():
    """A full DR drill (fresh backup, restore into a sandbox, integrity + SLA checks) passes."""
    result = run_dr_restore_drill()

    assert result["status"] == "SUCCESS", result
    # The backup archive's SHA-256 was verified before restore.
    assert result["sha256_verified"] is True
    # Schema was restored (the app DB always has tables); row count is
    # data-dependent, so only assert the field is present and sane.
    assert result["restored_tables_count"] >= 1
    assert result["restored_rows_count"] >= 0
    # Recovery objectives are met.
    assert result["rto_sla_met"] is True
    assert result["rpo_sla_met"] is True
    assert result["restore_duration_seconds"] <= result["rto_sla_seconds"]
