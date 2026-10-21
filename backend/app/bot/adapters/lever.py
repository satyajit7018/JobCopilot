"""
JobCopilot - Lever ATS Automation Adapter
Fills Lever.co application postings: contact details, links, resume upload and
the custom questions the user has already answered.
"""

from pathlib import Path
from typing import Any, Dict, Optional

try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore

from app.bot.form import answer_for, fill_field
from app.core.models import CandidateProfile


class LeverAdapter:
    """Specialized automation handler for Lever.co application forms."""

    @classmethod
    async def fill_application(
        cls,
        page: Page,
        profile: CandidateProfile,
        tailored_resume_path: Optional[Path] = None,
        user_id: str = "",
        company: str = "",
        role: str = "",
        job_id: str = "",
    ) -> Dict[str, Any]:
        """Fills standard and custom fields on a Lever application page."""
        filled_fields: Dict[str, Any] = {}

        # 1-4. Name, email, phone, current employer
        for name, value in (
            ("name", profile.full_name),
            ("email", profile.email),
            ("phone", profile.phone),
            ("org", profile.preferences.current_employer),
        ):
            if await fill_field(page, f"input[name='{name}']", value):
                filled_fields[name] = value

        # 5. Social URLs (LinkedIn, GitHub, Portfolio)
        urls_map = [
            ("input[name*='urls[LinkedIn]' i], input[name*='linkedin' i]", profile.linkedin_url),
            ("input[name*='urls[GitHub]' i], input[name*='github' i]", profile.github_url),
            ("input[name*='urls[Portfolio]' i], input[name*='portfolio' i], input[name*='website' i]", profile.portfolio_url)
        ]
        for sel, val in urls_map:
            if await fill_field(page, sel, val):
                filled_fields[sel] = val

        # 6. Resume File Upload
        if tailored_resume_path and Path(tailored_resume_path).exists():
            file_input = await page.query_selector("input[type='file'][name*='resume' i], input[type='file']")
            if file_input:
                await file_input.set_input_files(str(tailored_resume_path))
                filled_fields["resume_uploaded"] = str(tailored_resume_path)

        # 7. Custom questions the user has answered before. The rest stay empty for the user.
        for card in await page.query_selector_all(".application-question, .custom-question"):
            text_label = (await card.inner_text()).split('\n')[0].strip()
            if not text_label:
                continue
            answer = answer_for(text_label, profile, user_id=user_id, company=company, role=role, job_id=job_id)
            if answer and await fill_field(page, await card.query_selector("input[type='text'], textarea"), answer):
                filled_fields[text_label] = answer

        return filled_fields
