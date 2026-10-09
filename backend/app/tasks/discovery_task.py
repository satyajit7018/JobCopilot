"""
JobCopilot - Hourly job search for every user.

Celery beat triggers this at minute 7 of every hour; postings are fetched once and
only new ones are scored for each user (see DiscoveryOrchestrator.run_for_all_users).
"""

import asyncio
import logging

from app.tasks.celery_app import USE_CELERY, celery_app

logger = logging.getLogger("jobcopilot.tasks.discovery")


def run_hourly_discovery() -> dict:
    # A fresh orchestrator per run: each asyncio.run() is a new event loop.
    from app.discovery.orchestrator import DiscoveryOrchestrator
    return asyncio.run(DiscoveryOrchestrator().run_for_all_users())


if celery_app and USE_CELERY:
    @celery_app.task(name="jobcopilot.low.hourly_discovery", ignore_result=True,
                     soft_time_limit=50 * 60, time_limit=55 * 60)
    def hourly_discovery():  # pragma: no cover - runs in the Celery worker
        result = run_hourly_discovery()
        logger.info("hourly discovery finished: %s", result)
        return result
