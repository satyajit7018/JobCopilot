"""
JobCopilot - Universal ATS Form Adapter & Portal Dispatcher
Detects ATS portal signatures (Greenhouse, Lever, Ashby, Workday, etc.)
and dispatches automation with heuristic fallback.
"""

from pathlib import Path
from typing import Dict, Any, Optional
try:
    from playwright.async_api import Page
except ImportError:
    Page = Any  # type: ignore

from app.core.models import CandidateProfile
from app.core.vector_vault import vault
from app.bot.human_behavior import HumanBehaviorEngine
from app.bot.adapters.greenhouse import GreenhouseAdapter
from app.bot.adapters.lever import LeverAdapter


class UniversalATSAdapter:
    """Detects ATS type and orchestrates autonomous form filling."""

    @classmethod
    def detect_platform(cls, url: str, page_content: str) -> str:
        """Identifies ATS portal platform from URL and DOM signatures."""
        url_low = url.lower()
        content_low = page_content.lower()

        if "greenhouse.io" in url_low or "gh_jid" in url_low or "greenhouse" in content_low:
            return "Greenhouse"
        if "lever.co" in url_low or "lever" in content_low:
            return "Lever"
        if "ashbyhq.com" in url_low or "ashby" in content_low:
            return "Ashby"
        if "myworkdayjobs.com" in url_low or "workday" in content_low:
            return "Workday"
        return "Universal"

    @classmethod
    async def fill_form_heuristics(
        cls,
        page: Page,
        profile: CandidateProfile,
        tailored_resume_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Universal heuristic fallback matching input labels and placeholders."""
        filled = {}

        # 1. Fill Text Inputs
        inputs = await page.query_selector_all("input[type='text'], input[type='email'], input[type='tel'], textarea")
        for inp in inputs:
            # Check attribute hints
            name_attr = (await inp.get_attribute("name") or "").lower()
            id_attr = (await inp.get_attribute("id") or "").lower()
            placeholder = (await inp.get_attribute("placeholder") or "").lower()
            aria_label = (await inp.get_attribute("aria-label") or "").lower()
            combined_hint = f"{name_attr} {id_attr} {placeholder} {aria_label}"

            if any(k in combined_hint for k in ["first", "fname"]) and not any(k in combined_hint for k in ["last", "lname"]):
                val = profile.full_name.split()[0]
                await HumanBehaviorEngine.human_type(page, inp, val)
                filled["first_name"] = val
            elif any(k in combined_hint for k in ["last", "lname"]):
                parts = profile.full_name.split()
                val = " ".join(parts[1:]) if len(parts) > 1 else parts[0]
                await HumanBehaviorEngine.human_type(page, inp, val)
                filled["last_name"] = val
            elif any(k in combined_hint for k in ["full_name", "fullname", "name"]) and "company" not in combined_hint:
                await HumanBehaviorEngine.human_type(page, inp, profile.full_name)
                filled["name"] = profile.full_name
            elif "email" in combined_hint:
                await HumanBehaviorEngine.human_type(page, inp, profile.email)
                filled["email"] = profile.email
            elif any(k in combined_hint for k in ["phone", "tel", "mobile"]):
                await HumanBehaviorEngine.human_type(page, inp, profile.phone)
                filled["phone"] = profile.phone
            elif "linkedin" in combined_hint and profile.linkedin_url:
                await HumanBehaviorEngine.human_type(page, inp, profile.linkedin_url)
                filled["linkedin"] = profile.linkedin_url
            elif "github" in combined_hint and profile.github_url:
                await HumanBehaviorEngine.human_type(page, inp, profile.github_url)
                filled["github"] = profile.github_url

        # 2. File Upload
        if tailored_resume_path and Path(tailored_resume_path).exists():
            file_input = await page.query_selector("input[type='file']")
            if file_input:
                await file_input.set_input_files(str(tailored_resume_path))
                filled["resume_uploaded"] = str(tailored_resume_path)

        return filled

    @classmethod
    async def fill_application(
        cls,
        page: Page,
        profile: CandidateProfile,
        tailored_resume_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """Dispatches filling to the specialized adapter or heuristic fallback."""
        url = page.url
        content = await page.content()
        platform = cls.detect_platform(url, content)

        if platform == "Greenhouse":
            return await GreenhouseAdapter.fill_application(page, profile, tailored_resume_path)
        elif platform == "Lever":
            return await LeverAdapter.fill_application(page, profile, tailored_resume_path)
        else:
            return await cls.fill_form_heuristics(page, profile, tailored_resume_path)
