"""
JobCopilot - Greenhouse ATS Automation Adapter
Automates Greenhouse application pages with resume upload, custom questions,
and demographic field matching.
"""

from pathlib import Path
from typing import Dict, Any, Optional
from playwright.async_api import Page

from app.core.models import CandidateProfile
from app.core.vector_vault import vault
from app.bot.human_behavior import HumanBehaviorEngine


class GreenhouseAdapter:
    """Specialized automation handler for Greenhouse.io job application forms."""

    @classmethod
    async def fill_application(
        cls,
        page: Page,
        profile: CandidateProfile,
        tailored_resume_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Fills standard and custom fields on a Greenhouse application page."""
        filled_fields = {}

        # 1. First Name & Last Name
        name_parts = profile.full_name.split()
        first_name = name_parts[0] if name_parts else profile.full_name
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        if await page.query_selector("#first_name"):
            await HumanBehaviorEngine.human_type(page, "#first_name", first_name)
            filled_fields["first_name"] = first_name

        if await page.query_selector("#last_name"):
            await HumanBehaviorEngine.human_type(page, "#last_name", last_name or first_name)
            filled_fields["last_name"] = last_name or first_name

        # 2. Email
        if await page.query_selector("#email"):
            await HumanBehaviorEngine.human_type(page, "#email", profile.email)
            filled_fields["email"] = profile.email

        # 3. Phone
        if await page.query_selector("#phone"):
            await HumanBehaviorEngine.human_type(page, "#phone", profile.phone)
            filled_fields["phone"] = profile.phone

        # 4. Resume File Upload
        if tailored_resume_path and Path(tailored_resume_path).exists():
            file_input = await page.query_selector("input[type='file'][name*='resume' i], input[type='file']")
            if file_input:
                await file_input.set_input_files(str(tailored_resume_path))
                filled_fields["resume_uploaded"] = str(tailored_resume_path)

        # 5. LinkedIn & GitHub URLs
        if profile.linkedin_url:
            li_input = await page.query_selector("input[name*='linkedin' i], input[id*='linkedin' i]")
            if li_input:
                await HumanBehaviorEngine.human_type(page, li_input, profile.linkedin_url)
                filled_fields["linkedin"] = profile.linkedin_url

        if profile.github_url:
            gh_input = await page.query_selector("input[name*='github' i], input[id*='github' i], input[name*='website' i]")
            if gh_input:
                await HumanBehaviorEngine.human_type(page, gh_input, profile.github_url)
                filled_fields["github"] = profile.github_url

        # 6. Custom Recruiter Questions via Knowledge Vault
        custom_fields = await page.query_selector_all(".field label, .custom-question label")
        for label_el in custom_fields:
            label_text = (await label_el.inner_text()).strip()
            if not label_text:
                continue

            # Query Knowledge Vault
            resolved_answer, score, _ = vault.get_answer_for_question(
                label_text,
                context={"company": "Company", "top_skills": ", ".join(profile.skills[:3])}
            )

            if resolved_answer and score >= 0.65:
                # Find sibling or child input/textarea
                parent = await label_el.evaluate_handle("el => el.closest('.field') || el.parentElement")
                input_el = await parent.query_selector("input[type='text'], textarea")
                if input_el:
                    await HumanBehaviorEngine.human_type(page, input_el, resolved_answer)
                    filled_fields[label_text] = resolved_answer

        return filled_fields
