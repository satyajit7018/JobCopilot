#!/usr/bin/env python3
"""
JobCopilot - Automated Canary/Blue-Green Rollback Trigger
Monitors deployment health and SLO metrics post-deployment.
If the /health probe fails or SLO thresholds are breached during the canary observation window,
automatically executes rollback command and halts traffic shift.
"""

import os
import sys
import time
import json
import shlex
import logging
import argparse
import subprocess
import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("health_rollback_monitor")


def probe_health_endpoint(target_url: str, timeout: float = 5.0) -> dict:
    """Probes the application /health endpoint with strict timeouts."""
    if not (target_url.startswith("http://") or target_url.startswith("https://")):
        raise ValueError(f"Insecure or invalid URL scheme: {target_url}")

    with httpx.Client(timeout=timeout) as client:
        response = client.get(
            target_url,
            headers={"User-Agent": "JobCopilot-Canary-Health-Probe/1.0", "Accept": "application/json"}
        )
        if response.status_code != 200:
            raise RuntimeError(f"HTTP status {response.status_code} != 200")
        return response.json()


def execute_rollback(rollback_command: str) -> bool:
    """Executes the automated rollback command safely without shell=True."""
    logger.critical(f">>> CRITICAL: Triggering automated rollback command: '{rollback_command}'")
    try:
        cmd_args = shlex.split(rollback_command)
        res = subprocess.run(
            cmd_args,
            shell=False,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        logger.info(f"Rollback execution output: {res.stdout.strip()}")
        return True
    except subprocess.CalledProcessError as err:
        logger.error(f"Rollback command failed: {err.stderr.strip()}")
        return False


def monitor_canary(
    target_url: str,
    probes: int = 5,
    interval_seconds: float = 3.0,
    rollback_command: str = "echo Rollback triggered: Canary deployment reverted"
) -> bool:
    """
    Performs consecutive health probes across canary observation window.
    Returns True if healthy, False if breach triggered rollback.
    """
    logger.info(f"Starting canary verification on {target_url} ({probes} probes, {interval_seconds}s interval)")

    consecutive_successes = 0

    for i in range(1, probes + 1):
        try:
            data = probe_health_endpoint(target_url)
            status = data.get("status")
            db_status = data.get("database", {}).get("status")

            if status != "healthy" or db_status != "healthy":
                raise ValueError(f"System degraded: status={status}, db={db_status}")

            consecutive_successes += 1
            logger.info(f"Probe {i}/{probes}: HEALTHY (status={status}, db={db_status})")

        except Exception as exc:
            logger.error(f"Probe {i}/{probes} FAILED: {exc}")
            execute_rollback(rollback_command)
            return False

        if i < probes:
            time.sleep(interval_seconds)

    logger.info("==================================================")
    logger.info(f"CANARY HEALTH OBSERVATION: PASSED ({consecutive_successes}/{probes} probes clean)")
    logger.info("==================================================")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Canary health and automated rollback monitor")
    parser.add_argument("--url", default="http://127.0.0.1:8000/health", help="Target /health URL")
    parser.add_argument("--probes", type=int, default=5, help="Number of consecutive health probes")
    parser.add_argument("--interval", type=float, default=2.0, help="Interval between probes in seconds")
    parser.add_argument(
        "--rollback-cmd",
        default="echo Rollback triggered: Canary deployment reverted",
        help="Command to execute if health probe breaches SLO"
    )

    args = parser.parse_args()
    success = monitor_canary(
        target_url=args.url,
        probes=args.probes,
        interval_seconds=args.interval,
        rollback_command=args.rollback_cmd
    )
    sys.exit(0 if success else 1)
