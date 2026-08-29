"""
JobCopilot - Typed Data Models & Schemas
Covers Candidate Profile, Knowledge Vault, Job Records, and HITL Events.
"""

from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field


class SlotType(str, Enum):
    EXACT_PARAM = "EXACT_PARAM"
    TECH_YEARS = "TECH_YEARS"
    PARAMETRIC_ESSAY = "PARAMETRIC_ESSAY"
    FREEFORM = "FREEFORM"
    SELECTION = "SELECTION"


class ApplicationStatus(str, Enum):
    DISCOVERED = "DISCOVERED"
    QUEUED = "QUEUED"
    IN_PROGRESS = "IN_PROGRESS"
    HITL_REQUIRED = "HITL_REQUIRED"
    SUBMITTED = "SUBMITTED"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    RESPONDED = "RESPONDED"
    INTERVIEW = "INTERVIEW"
    REJECTED = "REJECTED"
    OFFER = "OFFER"


class Education(BaseModel):
    degree: str
    institution: str
    graduation_year: Optional[str] = None
    gpa: Optional[str] = None
    coursework: List[str] = Field(default_factory=list)


class WorkExperience(BaseModel):
    company: str
    title: str
    start_date: str
    end_date: str
    location: Optional[str] = None
    highlights: List[str] = Field(default_factory=list)
    tech_stack: List[str] = Field(default_factory=list)


class Project(BaseModel):
    name: str
    description: str
    technologies: List[str] = Field(default_factory=list)
    link: Optional[str] = None
    metrics: Optional[str] = None


class RecruiterPreferences(BaseModel):
    current_ctc: str = "0 LPA"
    expected_ctc: str = "15 LPA"
    notice_period_days: int = 0
    work_authorization: str = "Citizen"
    requires_sponsorship: bool = False
    willing_to_relocate: bool = True
    remote_preference: str = "Remote / Hybrid / On-site"
    earliest_start_date: str = "Immediate"
    years_of_experience: float = 1.0


class CandidateProfile(BaseModel):
    id: str = "default_user"
    full_name: str
    email: str
    phone: str
    location: str
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    summary: str = ""
    education: List[Education] = Field(default_factory=list)
    experience: List[WorkExperience] = Field(default_factory=list)
    projects: List[Project] = Field(default_factory=list)
    skills: List[str] = Field(default_factory=list)
    certifications: List[str] = Field(default_factory=list)
    preferences: RecruiterPreferences = Field(default_factory=RecruiterPreferences)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class VaultEntry(BaseModel):
    qa_id: str
    slot_type: SlotType
    slot_key: str  # e.g., 'expected_ctc', 'TECH_YEARS:Python', 'why_join_company'
    question_pattern: str
    embedding: List[float] = Field(default_factory=list)
    answer_template: str
    dynamic_variables: List[str] = Field(default_factory=list)
    usage_count: int = 0
    last_used_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class JobListing(BaseModel):
    job_id: str
    fingerprint: str  # Hash of company + title + location for deduplication
    platform: str     # YC, Wellfound, Naukri, Greenhouse, Lever, Ashby, Indeed
    company: str
    title: str
    location: str = "Remote / India"
    url: str
    description: str = ""
    posted_date: Optional[str] = None
    match_score: float = 0.0
    priority_score: float = 0.0
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    applied_at: Optional[str] = None
    notes: Optional[str] = None


class HITLEvent(BaseModel):
    event_id: str
    job_id: str
    company: str
    role_title: str
    question_text: str
    input_type: str = "textarea"  # text, textarea, select, file, captcha
    options: List[str] = Field(default_factory=list)
    ai_suggested_draft: str = ""
    user_answer: Optional[str] = None
    status: str = "PENDING"  # PENDING, RESOLVED, SKIPPED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
