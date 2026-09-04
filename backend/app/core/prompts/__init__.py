"""
JobCopilot - Versioned Prompt Engineering & AI Intelligence Module
Provides structured, versioned, and testable prompt templates for resume tailoring,
STAR interview evaluation, salary negotiation, and outreach.
"""

from app.core.prompts.tailoring_prompts import TailoringPrompts
from app.core.prompts.interview_prompts import InterviewPrompts
from app.core.prompts.negotiation_prompts import NegotiationPrompts
from app.core.prompts.cover_letter_prompts import CoverLetterPrompts

__all__ = [
    "TailoringPrompts",
    "InterviewPrompts",
    "NegotiationPrompts",
    "CoverLetterPrompts"
]
