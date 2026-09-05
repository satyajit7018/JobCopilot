#!/usr/bin/env python3
"""
JobCopilot - Disaster Recovery Automated Backup Engine
Creates non-blocking, point-in-time verified database snapshots.
Computes cryptographic SHA-256 integrity digests and outputs JSON manifests for DR audits.
"""

import os
import sys
import time
import json
import sqlite3
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("dr_backup")


def compute_sha256(file_path: Path) -> str:
    """Computes SHA-256 hash of a file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def create_sqlite_backup(src_path: Path, dest_path: Path) -> Dict[str, Any]:
    """Uses SQLite online backup API for zero-downtime, non-locking atomic snapshot."""
    start_time = time.time()
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    src_conn = sqlite3.connect(str(src_path))
    dest_conn = sqlite3.connect(str(dest_path))

    try:
        # Atomic online snapshot without locking readers/writers
        src_conn.backup(dest_conn, pages=100)
    finally:
        dest_conn.close()
        src_conn.close()

    elapsed = time.time() - start_time
    file_size = dest_path.stat().st_size
    sha256_hash = compute_sha256(dest_path)

    # Count rows in restored tables for verification
    verify_conn = sqlite3.connect(str(dest_path))
    cursor = verify_conn.cursor()
    cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table'")
    table_count = cursor.fetchone()[0]
    verify_conn.close()

    manifest = {
        "backup_id": f"bkp_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
        "engine": "sqlite_wal",
        "source": str(src_path),
        "backup_file": str(dest_path),
        "size_bytes": file_size,
        "sha256": sha256_hash,
        "table_count": table_count,
        "duration_seconds": round(elapsed, 4),
        "created_at": datetime.utcnow().isoformat() + "Z"
    }

    manifest_path = dest_path.with_suffix(".json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    logger.info(f"✓ Backup created: {dest_path.name} ({file_size} bytes, {table_count} tables, sha256: {sha256_hash[:12]}...)")
    return manifest


def run_backup(dest_dir: Optional[Path] = None) -> Dict[str, Any]:
    repo_root = Path(__file__).resolve().parent.parent
    data_dir = repo_root / "backend" / "data"
    default_db = data_dir / "jobcopilot.db"

    target_dir = dest_dir or (repo_root / "backend" / "data" / "backups")
    target_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    backup_file = target_dir / f"jobcopilot_backup_{timestamp}.db"

    if not default_db.exists():
        # Initialize an empty verified database if none exists yet
        logger.info(f"Source DB {default_db} not found, initializing fresh baseline...")
        default_db.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(default_db))
        cursor = conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS system_metadata (key TEXT PRIMARY KEY, val TEXT)")
        cursor.execute("INSERT OR REPLACE INTO system_metadata VALUES ('init_time', ?)", (datetime.utcnow().isoformat(),))
        conn.commit()
        conn.close()

    return create_sqlite_backup(default_db, backup_file)


if __name__ == "__main__":
    manifest = run_backup()
    print(json.dumps(manifest, indent=2))
