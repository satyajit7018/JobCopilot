"""
JobCopilot - Lever ATS Automation Adapter
Automates Lever.co application postings with resume upload,
social profile links, and dynamic custom questions.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import Page

from app.core.models import CandidateProfile
from app.core.vector_vault import vault
from app.bot.human_behavior import HumanBehaviorEngine


class LeverAdapter:
    """Specialized automation handler for Lever.co application forms."""

    @classmethod
    async def fill_application(
        cls,
        page: Page,
        profile: CandidateProfile,
        tailored_resume_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Fills standard and custom fields on a Lever application page."""
        filled_fields = {}

        # 1. Full Name
        if await page.query_selector("input[name='name']"):
            await HumanBehaviorEngine.human_type(page, "input[name='name']", profile.full_name)
            filled_fields["name"] = profile.full_name

        # 2. Email
        if await page.query_selector("input[name='email']"):
            await HumanBehaviorEngine.human_type(page, "input[name='email']", profile.email)
            filled_fields["email"] = profile.email

        # 3. Phone
        if await page.query_selector("input[name='phone']"):
            await HumanBehaviorEngine.human_type(page, "input[name='phone']", profile.phone)
            filled_fields["phone"] = profile.phone

        # 4. Current Organization / Employer
        if profile.preferences.current_employer and await page.query_selector("input[name='org']"):
            await HumanBehaviorEngine.human_type(page, "input[name='org']", profile.preferences.current_employer)
            filled_fields["org"] = profile.preferences.current_employer

        # 5. Social URLs (LinkedIn, GitHub, Portfolio)
        urls_map = [
            ("input[name*='urls[LinkedIn]' i], input[name*='linkedin' i]", profile.linkedin_url),
            ("input[name*='urls[GitHub]' i], input[name*='github' i]", profile.github_url),
            ("input[name*='urls[Portfolio]' i], input[name*='portfolio' i], input[name*='website' i]", profile.portfolio_url)
        ]
        for sel, val in urls_map:
            if val:
                input_el = await page.query_selector(sel)
                if input_el:
                    await HumanBehaviorEngine.human_type(page, input_el, val)
                    filled_fields[sel] = val

        # 6. Resume File Upload
        if tailored_resume_path and Path(tailored_resume_path).exists():
            file_input = await page.query_selector("input[type='file'][name*='resume' i], input[type='file']")
            if file_input:
                await file_input.set_input_files(str(tailored_resume_path))
                filled_fields["resume_uploaded"] = str(tailored_resume_path)

        # 7. Custom Questions via Knowledge Vault
        custom_cards = await page.query_selector_all(".application-question, .custom-question")
        for card in custom_cards:
            text_label = (await card.inner_text()).split('\n')[0].strip()
            if not text_label:
                continue

            resolved_answer, score, _ = vault.get_answer_for_question(text_label)
            if resolved_answer and score >= 0.65:
                inp = await card.query_selector("input[type='text'], textarea")
                if inp:
                    await HumanBehaviorEngine.human_type(page, inp, resolved_answer)
                    filled_fields[text_label] = resolved_answer

        return filled_fields
