"""
JobCopilot - Milestone 4 End-to-End Test Suite
Tests Stealth Chromium browser evasion, Human-Likeness physics,
ATS platform adapters, atomic state checkpointing, and HITL self-learning loops.
"""

import sys
import uuid
import time
from pathlib import Path
import pytest

# Skip this entire module when Playwright is not installed in the environment
pytest.importorskip("playwright", reason="Playwright browser driver not installed — skipping Milestone 4 browser automation tests")
from playwright.async_api import async_playwright  # type: ignore

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.models import CandidateProfile, RecruiterPreferences, JobListing, ApplicationStatus
from app.core.database import DatabaseManager
from app.core.vector_vault import KnowledgeVault
from app.bot.stealth import StealthEngine
from app.bot.human_behavior import HumanBehaviorEngine
from app.bot.adapters.greenhouse import GreenhouseAdapter
from app.bot.adapters.lever import LeverAdapter
from app.bot.adapters.universal import UniversalATSAdapter
from app.bot.checkpoint import CheckpointManager
from app.bot.hitl_agent import HITLAgent


class TestMilestone4:

    @pytest.fixture(autouse=True)
    def setup_candidate(self, tmp_path):
        self.db_path = tmp_path / "test_m4.db"
        self.db = DatabaseManager(self.db_path)
        self.profile = CandidateProfile(
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            linkedin_url="https://linkedin.com/in/satyajit-nayak",
            github_url="https://github.com/satyajit7018",
            skills=["Python", "FastAPI", "PyTorch", "Docker"],
            preferences=RecruiterPreferences(
                expected_ctc="20 LPA",
                current_employer="CurrentTech"
            )
        )

    # 1. Test Stealth Playwright Context & Webdriver Evasion
    @pytest.mark.asyncio
    async def test_stealth_evasion(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            context = await StealthEngine.create_stealth_context(browser)
            page = await context.new_page()
            await page.goto("about:blank")

            webdriver_val = await page.evaluate("() => navigator.webdriver")
            assert webdriver_val is None

            has_chrome = await page.evaluate("() => !!window.navigator.chrome && !!window.navigator.chrome.runtime")
            assert has_chrome is True

            plugins_len = await page.evaluate("() => navigator.plugins.length")
            assert plugins_len >= 2

            await browser.close()

    # 2. Test Human-Likeness Physics & Keystroke Rhythm
    @pytest.mark.asyncio
    async def test_human_physics(self):
        path = HumanBehaviorEngine.generate_mouse_path((50.0, 50.0), (300.0, 200.0), steps=15)
        assert len(path) == 16
        assert path[0] == (50.0, 50.0)

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.set_content('<input type="text" id="inp">')

            t0 = time.time()
            await HumanBehaviorEngine.human_type(page, "#inp", "Python")
            t_diff = time.time() - t0

            val = await page.input_value("#inp")
            assert val == "Python"
            assert t_diff >= 0.20  # Verified not instantaneous machine typing

            await browser.close()

    # 3. Test Form Adapters & Universal Heuristics
    @pytest.mark.asyncio
    async def test_form_adapters(self):
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Greenhouse Simulation
            await page.set_content("""
            <form id="app">
              <input type="text" id="first_name">
              <input type="text" id="last_name">
              <input type="email" id="email">
            </form>
            """)
            gh_res = await GreenhouseAdapter.fill_application(page, self.profile)
            assert gh_res["first_name"] == "Satyajit"
            assert gh_res["email"] == "scorpionsatyajit@gmail.com"

            # Lever Simulation
            await page.set_content("""
            <form class="lever">
              <input type="text" name="name">
              <input type="text" name="org">
            </form>
            """)
            lv_res = await LeverAdapter.fill_application(page, self.profile)
            assert lv_res["name"] == "Satyajit Nayak"
            assert lv_res["org"] == "CurrentTech"

            await browser.close()

    # 4. Test State Checkpoint Persist & Clear
    def test_state_checkpointing(self):
        jid = f"chk_test_{uuid.uuid4().hex[:6]}"
        saved = CheckpointManager.save_step(
            job_id=jid,
            current_step=1,
            total_steps=3,
            filled_inputs={"name": "Satyajit"},
            last_url="https://jobs.lever.co/stripe"
        )
        assert saved.current_step == 1

        retrieved = CheckpointManager.get_step(jid)
        assert retrieved is not None
        assert retrieved.filled_inputs["name"] == "Satyajit"

        CheckpointManager.clear(jid)
        assert CheckpointManager.get_step(jid) is None

    # 5. Test HITL Self-Learning Resolver
    @pytest.mark.asyncio
    async def test_hitl_self_learning(self):
        event = await HITLAgent.request_human_input(
            job_id="job_hitl_unit",
            company="Perplexity",
            role_title="AI Engineer",
            question_text="Are you authorized to work in the US?"
        )
        assert event.status == "PENDING"

        # Resolve
        from app.core.database import db
        db.resolve_hitl_event(event.event_id, "Citizen / Permanent Resident", user_id="default")

        ans = await HITLAgent.wait_for_resolution(event.event_id, poll_interval=0.05, max_timeout=2.0, user_id="default")
        assert ans == "Citizen / Permanent Resident"
