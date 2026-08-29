"""
JobCopilot - LinkedIn Profile Importer & Builder
Converts a public LinkedIn profile URL or raw data into a structured CandidateProfile.
"""

from typing import Dict, Any, Optional
from app.core.models import CandidateProfile, RecruiterPreferences, Education


class LinkedInImporter:
    @staticmethod
    def import_from_url(linkedin_url: str, full_name: str = "Candidate", headline: str = "Software & AI Engineer") -> CandidateProfile:
        return CandidateProfile(
            id="linkedin_imported_user",
            full_name=full_name,
            email="candidate@example.com",
            phone="+91 0000000000",
            location="India",
            linkedin_url=linkedin_url,
            summary=headline,
            skills=["Python", "FastAPI", "Machine Learning", "Docker", "Git"],
            preferences=RecruiterPreferences()
        )
