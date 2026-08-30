"""
JobCopilot - Typed Data Models & Schemas
Covers Candidate Profile, Knowledge Vault, Job Records, HITL Events, 
Multi-Resume Variants, Email Tracking, and Outreach Records.
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


class EmailIntent(str, Enum):
    CONFIRMATION = "CONFIRMATION"
    INTERVIEW_INVITE = "INTERVIEW_INVITE"
    ASSESSMENT = "ASSESSMENT"
    REJECTION = "REJECTION"
    FOLLOW_UP = "FOLLOW_UP"
    OTHER = "OTHER"


class OutreachChannel(str, Enum):
    ATS_FORM = "ATS_FORM"
    LINKEDIN_INMAIL = "LINKEDIN_INMAIL"
    COLD_EMAIL = "COLD_EMAIL"


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


class CategorizedSkills(BaseModel):
    languages: List[str] = Field(default_factory=list)
    frameworks: List[str] = Field(default_factory=list)
    cloud_devops: List[str] = Field(default_factory=list)
    databases: List[str] = Field(default_factory=list)
    tools_libraries: List[str] = Field(default_factory=list)


class DemographicPreferences(BaseModel):
    gender: Optional[str] = "Decline to Self-Identify"
    race_ethnicity: Optional[str] = "Decline to Self-Identify"
    veteran_status: Optional[str] = "Decline to Self-Identify"
    disability_status: Optional[str] = "Decline to Self-Identify"


class RecruiterPreferences(BaseModel):
    current_ctc: str = "0 LPA"
    expected_ctc: str = "15 LPA"
    target_currency: str = "INR"
    notice_period_days: int = 0
    work_authorization: str = "Citizen"
    requires_sponsorship: bool = False
    willing_to_relocate: bool = True
    remote_preference: str = "Remote / Hybrid / On-site"
    earliest_start_date: str = "Immediate"
    years_of_experience: float = 1.0
    why_looking_for_role: str = ""
    demographics: DemographicPreferences = Field(default_factory=DemographicPreferences)
    company_blacklist: List[str] = Field(default_factory=list)
    company_whitelist: List[str] = Field(default_factory=list)
    current_employer: Optional[str] = None  # Used for stealth mode employer blacklisting


class ResumeVariant(BaseModel):
    variant_id: str
    name: str  # e.g., "AI/ML Focus", "Backend Specialist", "Generalist"
    target_roles: List[str] = Field(default_factory=list)
    pdf_content_hash: Optional[str] = None
    tailored_text: str = ""
    is_default: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())


class UserRole(str, Enum):
    FREE = "FREE"
    PRO = "PRO"
    ELITE = "ELITE"
    ADMIN = "ADMIN"


class User(BaseModel):
    user_id: str
    email: str
    password_hash: str
    full_name: str = ""
    role: UserRole = UserRole.FREE
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class UserRegisterRequest(BaseModel):
    email: str
    password: str
    full_name: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: str
    password: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user_id: str
    email: str
    role: str


class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: str


class CandidateProfile(BaseModel):
    id: str = "default_user"
    user_id: str = "default"
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
    categorized_skills: CategorizedSkills = Field(default_factory=CategorizedSkills)
    certifications: List[str] = Field(default_factory=list)
    preferences: RecruiterPreferences = Field(default_factory=RecruiterPreferences)
    variants: List[ResumeVariant] = Field(default_factory=list)
    raw_resume_text: str = ""
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        """Pydantic compatibility helper"""
        return self.model_dump(*args, **kwargs)


class VaultEntry(BaseModel):
    qa_id: str
    user_id: str = "default"
    slot_type: SlotType
    slot_key: str  # e.g., 'expected_ctc', 'TECH_YEARS:Python', 'why_join_company'
    question_pattern: str
    embedding: List[float] = Field(default_factory=list)
    answer_template: str
    dynamic_variables: List[str] = Field(default_factory=list)
    usage_count: int = 0
    last_used_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class JobListing(BaseModel):
    job_id: str
    user_id: str = "default"
    fingerprint: str  # 64-bit SimHash of company + title + location + JD
    platform: str     # Greenhouse, Lever, Ashby, Workday, YC, Wellfound, Indeed, etc.
    company: str
    title: str
    location: str = "Remote / India"
    url: str
    description: str = ""
    salary_range: Optional[str] = None
    seniority_level: Optional[str] = None
    posted_date: Optional[str] = None
    match_score: float = 0.0
    priority_score: float = 0.0
    match_reasons: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)
    status: ApplicationStatus = ApplicationStatus.DISCOVERED
    submission_mode: Optional[str] = None  # DRY_RUN or LIVE
    applied_at: Optional[str] = None
    application_id: Optional[str] = None  # Internal ATS Reference ID scraped from confirmation
    confirmation_screenshot_path: Optional[str] = None
    notes: Optional[str] = None

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class HITLEvent(BaseModel):
    event_id: str
    user_id: str = "default"
    job_id: str
    company: str
    role_title: str
    question_text: str
    input_type: str = "textarea"  # text, textarea, select, file, captcha
    options: List[str] = Field(default_factory=list)
    ai_suggested_draft: str = ""
    user_answer: Optional[str] = None
    status: str = "PENDING"  # PENDING, RESOLVED, SKIPPED, EXPIRED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class OutreachRecord(BaseModel):
    outreach_id: str
    user_id: str = "default"
    job_id: str
    channel: OutreachChannel
    recipient_name: Optional[str] = None
    recipient_title: Optional[str] = None
    recipient_contact: Optional[str] = None  # Email address or LinkedIn profile URL
    message_content: str
    status: str = "DRAFT"  # DRAFT, QUEUED, SENT, REPLIED, FAILED
    sent_at: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class EmailMessage(BaseModel):
    message_id: str
    user_id: str = "default"
    sender: str
    recipient: str
    subject: str
    body_text: str
    received_at: str
    associated_job_id: Optional[str] = None
    intent: EmailIntent = EmailIntent.OTHER
    scheduling_links: List[str] = Field(default_factory=list)
    has_tracking_pixels: bool = False
    processed: bool = False

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class JobCheckpoint(BaseModel):
    job_id: str
    user_id: str = "default"
    current_step: int = 1
    total_steps: int = 1
    filled_inputs: Dict[str, Any] = Field(default_factory=dict)
    last_url: str = ""
    screenshot_path: Optional[str] = None
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)
