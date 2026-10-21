"""
JobCopilot - Greenhouse ATS Automation Adapter
Fills Greenhouse application pages: contact details, resume upload and the
custom questions the user has already answered.
"""

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore

from app.bot.form import answer_for, fill_field
from app.core.models import CandidateProfile


class GreenhouseAdapter:
    """Specialized automation handler for Greenhouse.io job application forms."""

    @classmethod
    async def fill_application(
        cls,
        page: Page,
        profile: CandidateProfile,
        tailored_resume_path: Optional[Path] = None,
        user_id: str = "",
        company: str = "",
        role: str = "",
    ) -> Dict[str, Any]:
        """Fills standard and custom fields on a Greenhouse application page."""
        filled_fields: Dict[str, Any] = {}

        # 1. First Name & Last Name
        name_parts = profile.full_name.split()
        first_name = name_parts[0] if name_parts else profile.full_name
        last_name = " ".join(name_parts[1:]) if len(name_parts) > 1 else ""

        first_name_input = await page.query_selector("#first_name, input[name*='first_name' i], input[name='job_application[first_name]'], input[autocomplete='given-name']")
        if await fill_field(page, first_name_input, first_name):
            filled_fields["first_name"] = first_name

        last_name_input = await page.query_selector("#last_name, input[name*='last_name' i], input[name='job_application[last_name]'], input[autocomplete='family-name']")
        if await fill_field(page, last_name_input, last_name or first_name):
            filled_fields["last_name"] = last_name or first_name

        # Single full name fallback if first/last split fields are not present
        if not first_name_input and not last_name_input:
            if await fill_field(page, "#name, input[name*='name' i], input[autocomplete='name']", profile.full_name):
                filled_fields["name"] = profile.full_name

        # 2. Email & 3. Phone
        if await fill_field(page, "#email, input[name*='email' i], input[name='job_application[email]'], input[autocomplete='email']", profile.email):
            filled_fields["email"] = profile.email
        if await fill_field(page, "#phone, input[name*='phone' i], input[name='job_application[phone]'], input[autocomplete='tel']", profile.phone):
            filled_fields["phone"] = profile.phone

        # 4. Resume File Upload
        if tailored_resume_path and Path(tailored_resume_path).exists():
            file_input = await page.query_selector("input[type='file'][name*='resume' i], input[type='file']")
            if file_input:
                await file_input.set_input_files(str(tailored_resume_path))
                filled_fields["resume_uploaded"] = str(tailored_resume_path)

        # 5. LinkedIn & GitHub URLs
        if await fill_field(page, "input[name*='linkedin' i], input[id*='linkedin' i]", profile.linkedin_url):
            filled_fields["linkedin"] = profile.linkedin_url
        if await fill_field(page, "input[name*='github' i], input[id*='github' i], input[name*='website' i]", profile.github_url):
            filled_fields["github"] = profile.github_url

        # 6. Custom questions the user has answered before. The rest stay empty for the user.
        for label_el in await page.query_selector_all(".field label, .custom-question label"):
            label_text = (await label_el.inner_text()).strip()
            if not label_text:
                continue
            answer = answer_for(label_text, profile, user_id=user_id, company=company, role=role)
            if not answer:
                continue
            parent = await label_el.evaluate_handle("el => el.closest('.field') || el.parentElement")
            input_el = await parent.query_selector("input[type='text'], textarea")
            if await fill_field(page, input_el, answer):
                filled_fields[label_text] = answer

        return filled_fields
