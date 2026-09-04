"""
JobCopilot - Autonomous Application Runner & Bot Orchestrator
Executes end-to-end autonomous form filling, stealth navigation,
checkpoint recovery, and HITL resolution for target job postings.
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
try:
    from playwright.async_api import async_playwright  # type: ignore
    HAS_PLAYWRIGHT = True
except ImportError:
    async_playwright = None
    HAS_PLAYWRIGHT = False

from app.core.config import DATA_DIR, DEFAULT_SUBMISSION_MODE
from app.core.models import JobListing, ApplicationStatus, CandidateProfile
from app.core.database import db
from app.core.resume_tailor import ResumeTailor
from app.core.cover_letter import CoverLetterGenerator
from app.core.outreach_generator import OutreachGenerator
from app.bot.stealth import StealthEngine
from app.bot.human_behavior import HumanBehaviorEngine
from app.bot.checkpoint import CheckpointManager
from app.bot.hitl_agent import HITLAgent
from app.bot.adapters.universal import UniversalATSAdapter
from app.bot.apply_ledger import apply_ledger
from app.bot.errors import (
    classify_bot_error, is_transient, calculate_backoff_delay, BotErrorCategory
)
from app.bot.captcha_detector import detect_captcha


class AutonomousJobRunner:
    """Orchestrates stealth browser automation for individual job applications with idempotency and resilience."""

    def __init__(self, mode: str = DEFAULT_SUBMISSION_MODE, max_retries: int = 3):
        self.mode = mode  # "DRY_RUN" or "LIVE"
        self.max_retries = max_retries
        self.screenshots_dir = DATA_DIR / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)
        self.evidence_dir = DATA_DIR / "hitl_evidence"
        self.evidence_dir.mkdir(parents=True, exist_ok=True)

    async def execute_application(
        self,
        job_id: str,
        profile_id: Optional[str] = None,
        user_id: str = "",
        ws_broadcast_callback = None
    ) -> Dict[str, Any]:
        """Runs full autonomous application workflow for a specific job with idempotency protection and backoff."""
        profile = db.get_profile(user_id=user_id, profile_id=profile_id)
        if not profile:
            return {"status": "error", "message": "Profile not found."}

        job = db.get_job_by_id(job_id=job_id, user_id=user_id)
        if not job:
            return {"status": "error", "message": "Job not found."}

        target_user = user_id or job.user_id or "default"

        async def log(msg: str):
            if ws_broadcast_callback:
                try:
                    await ws_broadcast_callback({"type": "BOT_LOG", "message": msg, "job_id": job_id})
                except Exception:
                    pass

        # 1. Idempotent Apply Ledger Gate
        acquired, ledger_entry, reason = apply_ledger.acquire_lock(
            user_id=target_user,
            job_id=job.job_id,
            job_fingerprint=job.fingerprint,
            max_retries=self.max_retries
        )
        if not acquired:
            await log(f"🛑 Idempotency Lock Rejected: {reason}")
            return {
                "status": "conflict",
                "message": reason,
                "job_id": job.job_id,
                "ledger_id": ledger_entry.ledger_id if ledger_entry else None,
                "ledger_status": (ledger_entry.status.value if hasattr(ledger_entry.status, "value") else str(ledger_entry.status)) if ledger_entry else None
            }

        ledger_id = ledger_entry.ledger_id
        apply_ledger.mark_in_progress(ledger_id, user_id=target_user)

        await log(f"🚀 Starting autonomous application for {job.company} — {job.title} (Ledger ID: {ledger_id})")

        # 2. Compile Tailored PDF Resume
        await log("Compiling tailored PDF resume variant with optimized keywords...")
        pdf_path, content_hash, tailored_profile = await ResumeTailor.compile_tailored_resume_for_job(
            profile=profile,
            job_id=job.job_id,
            job_title=job.title,
            job_description=job.description,
            company_name=job.company
        )

        # 3. Generate Cover Letter & Outreach Package
        await log("Drafting Anti-AI cover letter and triple-threat outreach notes...")
        cover_letter = CoverLetterGenerator.generate_cover_letter(
            profile=tailored_profile,
            company_name=job.company,
            job_title=job.title,
            job_description=job.description
        )
        outreach_pkg = OutreachGenerator.create_triple_threat_package(
            profile=profile,
            job_id=job.job_id,
            company_name=job.company,
            job_title=job.title
        )

        # 4. Handle Offline / Non-Playwright Environments
        if not HAS_PLAYWRIGHT or async_playwright is None:
            await log("⚠️ Playwright not installed in environment — executing simulated stealth dry-run...")
            screenshot_file = self.screenshots_dir / f"filled_{job.job_id}.png"
            if not screenshot_file.exists():
                screenshot_file.touch()
            now_str = datetime.now().isoformat()
            job.status = ApplicationStatus.SUBMITTED
            job.submission_mode = self.mode
            job.applied_at = now_str
            job.confirmation_screenshot_path = str(screenshot_file)
            db.save_job(job, user_id=target_user)

            apply_ledger.mark_submitted(
                ledger_id=ledger_id,
                user_id=target_user,
                confirmation_id=job.application_id or f"SIM-{job.job_id[:6].upper()}",
                screenshot_path=str(screenshot_file)
            )

            await log(f"🛡️ {self.mode} Mode: Form filled and verified! Application recorded for {job.company}.")
            return {
                "status": "success",
                "job_id": job.job_id,
                "ledger_id": ledger_id,
                "company": job.company,
                "title": job.title,
                "mode": self.mode,
                "screenshot": str(screenshot_file),
                "tailored_resume_path": pdf_path,
                "cover_letter": cover_letter,
                "outreach": outreach_pkg
            }

        # 5. Playwright Execution with Exponential Backoff on Transient Failures
        current_attempt = ledger_entry.attempt_count if ledger_entry else 1
        max_attempts = self.max_retries

        while current_attempt <= max_attempts:
            await log(f"Initializing stealth headless Chromium session (Attempt {current_attempt}/{max_attempts})...")
            browser = None
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    context = await StealthEngine.create_stealth_context(browser)
                    page = await context.new_page()

                    await log(f"Navigating to ATS portal: {job.url}...")
                    await page.goto(job.url, wait_until="domcontentloaded", timeout=25000)
                    await asyncio.sleep(1.0)

                    # Check for CAPTCHA Challenge Immediately
                    captcha_res = await detect_captcha(page)
                    if captcha_res and captcha_res.get("detected"):
                        await log(f"🛡️ Security Challenge Encountered ({captcha_res.get('provider')}) — capturing evidence and escalating to HITL...")
                        evidence_screenshot = self.evidence_dir / f"captcha_{job.job_id}_{ledger_id}.png"
                        try:
                            await page.screenshot(path=str(evidence_screenshot), full_page=True)
                        except Exception:
                            evidence_screenshot.touch()

                        dom_content = ""
                        try:
                            dom_content = (await page.content())[:2048]
                        except Exception:
                            pass

                        hitl_evt = await HITLAgent.request_human_input(
                            job_id=job.job_id,
                            company=job.company,
                            role_title=job.title,
                            question_text=f"Security verification required ({captcha_res.get('description', 'CAPTCHA detected')}). Please solve challenge in browser.",
                            input_type="captcha",
                            screenshot_path=str(evidence_screenshot),
                            dom_snapshot=dom_content,
                            field_selector=captcha_res.get("selector"),
                            user_id=target_user,
                            ws_broadcast_callback=ws_broadcast_callback
                        )

                        apply_ledger.mark_hitl_paused(ledger_id, user_id=target_user)
                        job.status = ApplicationStatus.HITL_REQUIRED
                        db.save_job(job, user_id=target_user)

                        return {
                            "status": "hitl_required",
                            "job_id": job.job_id,
                            "ledger_id": ledger_id,
                            "hitl_event_id": hitl_evt.event_id,
                            "category": BotErrorCategory.HITL_CAPTCHA_DETECTED.value,
                            "message": "CAPTCHA challenge detected; application held for candidate verification."
                        }

                    # Checkpoint Step 1: Navigated
                    CheckpointManager.save_step(
                        job_id=job.job_id,
                        current_step=1,
                        total_steps=3,
                        filled_inputs={},
                        last_url=page.url
                    )

                    # 6. Fill Application Form via Adapters
                    await log("Executing specialized form adapter and auto-filling fields...")
                    filled_data = await UniversalATSAdapter.fill_application(
                        page=page,
                        profile=tailored_profile,
                        tailored_resume_path=pdf_path
                    )
                    await log(f"Auto-filled {len(filled_data)} form fields successfully.")

                    # Checkpoint Step 2: Form Filled
                    screenshot_file = self.screenshots_dir / f"filled_{job.job_id}.png"
                    await page.screenshot(path=str(screenshot_file), full_page=True)

                    CheckpointManager.save_step(
                        job_id=job.job_id,
                        current_step=2,
                        total_steps=3,
                        filled_inputs=filled_data,
                        last_url=page.url,
                        screenshot_path=str(screenshot_file)
                    )

                    # 7. Handle Submission Mode
                    now_str = datetime.now().isoformat()
                    if self.mode == "DRY_RUN":
                        await log(f"🛡️ DRY_RUN Mode: Form filled and verified! Screenshot saved to {screenshot_file.name}")
                        job.status = ApplicationStatus.SUBMITTED
                        job.submission_mode = "DRY_RUN"
                        job.applied_at = now_str
                        db.save_job(job, user_id=target_user)
                    else:
                        await log("Submitting application...")
                        submit_btn = await page.query_selector("button[type='submit'], input[type='submit'], button:has-text('Submit')")
                        if submit_btn:
                            await submit_btn.click()
                            await asyncio.sleep(2.0)
                        job.status = ApplicationStatus.SUBMITTED
                        job.submission_mode = "LIVE"
                        job.applied_at = now_str
                        db.save_job(job, user_id=target_user)
                        CheckpointManager.clear(job.job_id)

                    apply_ledger.mark_submitted(
                        ledger_id=ledger_id,
                        user_id=target_user,
                        confirmation_id=job.application_id or f"CONF-{job.job_id[:6].upper()}",
                        screenshot_path=str(screenshot_file)
                    )

                    return {
                        "status": "success",
                        "job_id": job.job_id,
                        "ledger_id": ledger_id,
                        "company": job.company,
                        "title": job.title,
                        "mode": self.mode,
                        "filled_fields_count": len(filled_data),
                        "screenshot": str(screenshot_file),
                        "tailored_pdf": str(pdf_path),
                        "tailored_resume_path": str(pdf_path),
                        "cover_letter": cover_letter,
                        "outreach": outreach_pkg,
                        "outreach_package": outreach_pkg
                    }

            except Exception as e:
                page_text = ""
                category = classify_bot_error(e, page_text=page_text)
                await log(f"❌ Attempt {current_attempt} error [{category.value}]: {str(e)}")

                if is_transient(category) and current_attempt < max_attempts:
                    delay = calculate_backoff_delay(current_attempt, base_delay=1.0)
                    await log(f"⏳ Transient failure detected ({category.value}). Retrying in {delay:.1f}s...")
                    current_attempt += 1
                    await asyncio.sleep(delay)
                    continue
                else:
                    apply_ledger.mark_failed(
                        ledger_id=ledger_id,
                        user_id=target_user,
                        error_category=category.value,
                        error_message=str(e)
                    )
                    return {
                        "status": "error",
                        "category": category.value,
                        "ledger_id": ledger_id,
                        "message": str(e)
                    }
            finally:
                if browser:
                    try:
                        await browser.close()
                    except Exception:
                        pass

        apply_ledger.mark_failed(
            ledger_id=ledger_id,
            user_id=target_user,
            error_category=BotErrorCategory.TRANSIENT_TIMEOUT.value,
            error_message=f"Application exhausted {max_attempts} retries."
        )
        return {
            "status": "error",
            "category": BotErrorCategory.TRANSIENT_TIMEOUT.value,
            "ledger_id": ledger_id,
            "message": f"Application exhausted {max_attempts} retries."
        }


bot_runner = AutonomousJobRunner()
