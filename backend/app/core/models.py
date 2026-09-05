"""
JobCopilot - Typed Data Models & Schemas
Covers Candidate Profile, Knowledge Vault, Job Records, HITL Events, 
Multi-Resume Variants, Email Tracking, and Outreach Records.
"""

import uuid
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


class ApplyLedgerStatus(str, Enum):
    INITIATED = "INITIATED"
    IN_PROGRESS = "IN_PROGRESS"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"
    HITL_PAUSED = "HITL_PAUSED"
    CANCELLED = "CANCELLED"


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
    email_verified: bool = False
    impersonated_by: Optional[str] = None
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
    mfa_required: bool = False
    mfa_token: Optional[str] = None


class UserResponse(BaseModel):
    user_id: str
    email: str
    full_name: str
    role: str
    email_verified: bool = False
    created_at: str


class VerifyEmailRequest(BaseModel):
    token: str


class RequestPasswordResetRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


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
    created_at: Optional[str] = None
    interview_date: Optional[str] = None
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
    screenshot_path: Optional[str] = None
    dom_snapshot: Optional[str] = None
    field_selector: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    resolved_at: Optional[str] = None

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class ApplyLedgerEntry(BaseModel):
    ledger_id: str
    user_id: str = "default"
    job_id: str
    job_fingerprint: str
    status: ApplyLedgerStatus = ApplyLedgerStatus.INITIATED
    attempt_count: int = 1
    max_retries: int = 3
    last_error_category: Optional[str] = None
    last_error_message: Optional[str] = None
    confirmation_id: Optional[str] = None
    screenshot_path: Optional[str] = None
    idempotency_key: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

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


class OrgRole(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class Organization(BaseModel):
    org_id: str
    name: str
    slug: str
    owner_id: str
    plan_tier: str = "FREE"
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class Membership(BaseModel):
    membership_id: str
    org_id: str
    user_id: str
    role: OrgRole = OrgRole.MEMBER
    invited_by: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class AdminAuditLog(BaseModel):
    log_id: str
    admin_id: str
    action: str
    target_user_id: Optional[str] = None
    target_org_id: Optional[str] = None
    ip_address: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class CreateOrgRequest(BaseModel):
    name: str
    slug: Optional[str] = None


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    plan_tier: Optional[str] = None


class InviteMemberRequest(BaseModel):
    email: str
    role: OrgRole = OrgRole.MEMBER


class UpdateMemberRoleRequest(BaseModel):
    role: OrgRole


class OrgResponse(BaseModel):
    org_id: str
    name: str
    slug: str
    owner_id: str
    plan_tier: str = "FREE"
    created_at: str
    role: Optional[str] = None


class MemberResponse(BaseModel):
    membership_id: str
    org_id: str
    user_id: str
    email: str
    full_name: str
    role: str
    created_at: str


class AdminUserListResponse(BaseModel):
    users: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class AdminOrgListResponse(BaseModel):
    orgs: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


class AdminStatsResponse(BaseModel):
    total_users: int
    total_jobs: int
    total_applications: int
    active_subscriptions: Dict[str, int]
    total_organizations: int


class AdminImpersonateResponse(BaseModel):
    access_token: str
    impersonated_user_id: str
    impersonated_email: str
    admin_id: str
    token_type: str = "bearer"


class AccountExportResponse(BaseModel):
    user_id: str
    email: str
    exported_at: str
    data: Dict[str, Any]


class DeleteAccountRequest(BaseModel):
    confirm_email: str
    password: Optional[str] = None


# --- Epic F: MFA & TOTP Models ---
class MFACredentials(BaseModel):
    user_id: str
    secret: str
    backup_codes: List[Dict[str, Any]] = Field(default_factory=list)
    is_enabled: bool = False
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    backup_codes: List[str]
    message: str = "MFA setup initiated. Enter TOTP code to finalize activation."


class MFAVerifyRequest(BaseModel):
    code: str
    mfa_token: Optional[str] = None


class MFALoginChallengeRequest(BaseModel):
    mfa_token: str
    code: str


class MFADisableRequest(BaseModel):
    code: Optional[str] = None
    password: Optional[str] = None


# --- Epic F: Session & Device Management Models ---
class UserSession(BaseModel):
    session_id: str
    user_id: str
    token_jti: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    device_name: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    last_active: str = Field(default_factory=lambda: datetime.now().isoformat())
    is_active: bool = True

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class SessionResponse(BaseModel):
    session_id: str
    device_name: str
    ip_address: Optional[str] = None
    created_at: str
    last_active: str
    is_current: bool = False


class SessionListResponse(BaseModel):
    sessions: List[SessionResponse]
    total: int


# --- Epic F: Security Audit Log Models ---
class SecurityAuditLog(BaseModel):
    log_id: str
    user_id: Optional[str] = None
    event_type: str
    severity: str = "INFO"  # INFO, WARNING, CRITICAL
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class SecurityLogListResponse(BaseModel):
    logs: List[Dict[str, Any]]
    total: int
    limit: int
    offset: int


# --- Epic H: Data & ML Flywheel Models ---
class AnalyticsEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    event_type: str
    entity_type: str
    entity_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class EventBatch(BaseModel):
    events: List[AnalyticsEvent]


class CohortBucket(BaseModel):
    cohort_id: str
    start_date: str
    end_date: str
    total_candidates: int = 0
    applied_count: int = 0
    interview_count: int = 0
    offer_count: int = 0
    rejected_count: int = 0
    conversion_rate: float = 0.0


class ABVariant(BaseModel):
    variant_id: str
    name: str
    weight: float = 0.5
    description: Optional[str] = None


class ABExperiment(BaseModel):
    experiment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    name: str
    description: Optional[str] = None
    variants: List[ABVariant]
    status: str = "ACTIVE"  # ACTIVE, PAUSED, COMPLETED
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    ended_at: Optional[str] = None

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class ABAssignment(BaseModel):
    assignment_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    experiment_id: str
    user_id: str
    entity_id: str
    variant: str
    converted: bool = False
    converted_at: Optional[str] = None
    assigned_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


class ConversionSignal(BaseModel):
    signal_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    feature_type: str  # skill, seniority, platform, strategy
    feature_key: str
    sample_count: int = 0
    callback_count: int = 0
    conversion_rate: float = 0.0
    weight_multiplier: float = 1.0  # Bounded between 0.70x and 1.30x
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

    def dict(self, *args, **kwargs):
        return self.model_dump(*args, **kwargs)


