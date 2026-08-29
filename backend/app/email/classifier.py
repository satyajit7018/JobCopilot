"""
JobCopilot - 5-Way Recruiter Email Intent Classifier & Scheduling Link Extractor
Categorizes incoming recruiter emails into INTERVIEW_INVITE, ASSESSMENT,
REJECTION, CONFIRMATION, or OTHER, and extracts scheduling links.
"""

import re
from typing import List, Dict, Any, Tuple
from app.core.models import EmailIntent


class EmailClassifier:
    """Classifies recruiter email intent and extracts actionable scheduling links."""

    SCHEDULING_URL_REGEX = re.compile(
        r'https?://(?:calendly\.com|goodtime\.io|chilipiper\.com|savvycal\.com|meetings\.hubspot\.com|app\.reclaim\.ai|meet\.google\.com|zoom\.us|teams\.microsoft\.com|webex\.com)[^\s<>"\']+',
        re.IGNORECASE
    )

    OA_PLATFORMS_REGEX = re.compile(
        r'https?://[^\s<>"\']*(?:hackerrank\.com|codesignal\.com|coderbyte\.com|codility\.com|testgorilla\.com|byteboard\.dev)[^\s<>"\']*',
        re.IGNORECASE
    )

    @classmethod
    def extract_scheduling_links(cls, text: str) -> List[str]:
        """Extracts booking URLs from Calendly, GoodTime, Zoom, Google Meet, etc."""
        links = cls.SCHEDULING_URL_REGEX.findall(text)
        oa_links = cls.OA_PLATFORMS_REGEX.findall(text)
        return list(set(links + oa_links))

    @classmethod
    def classify_intent(cls, subject: str, body_text: str) -> Tuple[EmailIntent, float]:
        """
        Classifies incoming recruiter email into 5 deterministic buckets.
        Returns (intent, confidence_score).
        """
        combined = (subject + " " + body_text).lower()

        # 1. Rejection Indicators
        rejection_phrases = [
            "not moving forward", "pursue other candidates", "pursuing other candidates",
            "decided not to move forward", "decided to move forward with other",
            "not selected", "wish you the best in your search", "will not be moving forward",
            "unfortunately, we will not", "unsuccessful on this occasion", "at this time we have chosen"
        ]
        if any(p in combined for p in rejection_phrases):
            return EmailIntent.REJECTION, 0.95

        # 2. Online Assessment (OA) Indicators
        oa_phrases = [
            "hackerrank", "codesignal", "coderbyte", "codility", "take-home assignment",
            "take home assignment", "coding challenge", "online assessment",
            "technical assessment", "complete the assessment", "testgorilla"
        ]
        if any(p in combined for p in oa_phrases) or cls.OA_PLATFORMS_REGEX.search(combined):
            return EmailIntent.ASSESSMENT, 0.92

        # 3. Interview Invitation Indicators
        interview_phrases = [
            "schedule a phone screen", "schedule a call", "invitation to interview",
            "like to schedule a", "availability for a quick", "next steps in the interview",
            "technical interview", "phone interview", "chat with our team", "set up some time",
            "round of interviews", "speak with you about your application", "30-minute chat"
        ]
        if any(p in combined for p in interview_phrases) or cls.SCHEDULING_URL_REGEX.search(combined):
            return EmailIntent.INTERVIEW_INVITE, 0.94

        # 4. Application Confirmation
        confirmation_phrases = [
            "received your application", "thank you for applying", "application has been submitted",
            "we have received your application", "application received", "thanks for applying",
            "successfully submitted your application"
        ]
        if any(p in combined for p in confirmation_phrases):
            return EmailIntent.CONFIRMATION, 0.90

        # 5. Other / Inquiry
        return EmailIntent.OTHER, 0.75
