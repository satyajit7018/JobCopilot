"""
JobCopilot - Bot Error Taxonomy & Exponential Backoff Engine
Categorizes browser automation exceptions into transient vs terminal failures,
supporting smart retries and preventing repetitive doomed submissions.
"""

import random
from enum import Enum
from typing import Optional, Any


class BotErrorCategory(str, Enum):
    # Transient failures (safe to retry with exponential backoff)
    TRANSIENT_NETWORK = "TRANSIENT_NETWORK"
    TRANSIENT_TIMEOUT = "TRANSIENT_TIMEOUT"
    TRANSIENT_RATE_LIMIT = "TRANSIENT_RATE_LIMIT"
    TRANSIENT_SERVER_ERROR = "TRANSIENT_SERVER_ERROR"

    # Terminal failures (do not retry; immediate failure)
    TERMINAL_JOB_EXPIRED = "TERMINAL_JOB_EXPIRED"
    TERMINAL_AUTH_REQUIRED = "TERMINAL_AUTH_REQUIRED"
    TERMINAL_FORM_VALIDATION = "TERMINAL_FORM_VALIDATION"
    TERMINAL_ALREADY_APPLIED = "TERMINAL_ALREADY_APPLIED"
    TERMINAL_BLOCKED_WAF = "TERMINAL_BLOCKED_WAF"

    # Escalation needed
    HITL_CAPTCHA_DETECTED = "HITL_CAPTCHA_DETECTED"
    HITL_NOVEL_FIELD = "HITL_NOVEL_FIELD"

    # General / Fallback
    UNKNOWN = "UNKNOWN"


TRANSIENT_CATEGORIES = {
    BotErrorCategory.TRANSIENT_NETWORK,
    BotErrorCategory.TRANSIENT_TIMEOUT,
    BotErrorCategory.TRANSIENT_RATE_LIMIT,
    BotErrorCategory.TRANSIENT_SERVER_ERROR,
}


def is_transient(category: BotErrorCategory) -> bool:
    """Returns True if error is temporary and eligible for automated retry."""
    return category in TRANSIENT_CATEGORIES


class BotAutomationError(Exception):
    """Base exception for all bot automation errors."""
    def __init__(self, message: str, category: BotErrorCategory = BotErrorCategory.UNKNOWN):
        super().__init__(message)
        self.message = message
        self.category = category


class TransientBotError(BotAutomationError):
    """Temporary failure eligible for retry with backoff."""
    def __init__(self, message: str, category: BotErrorCategory = BotErrorCategory.TRANSIENT_NETWORK, retry_after: Optional[float] = None):
        super().__init__(message, category)
        self.retry_after = retry_after


class TerminalBotError(BotAutomationError):
    """Fatal submission failure that should not be retried."""
    def __init__(self, message: str, category: BotErrorCategory = BotErrorCategory.TERMINAL_JOB_EXPIRED):
        super().__init__(message, category)


class DuplicateApplicationError(TerminalBotError):
    """Candidate has already applied to this specific requisition."""
    def __init__(self, message: str = "Candidate has already applied to this job posting."):
        super().__init__(message, BotErrorCategory.TERMINAL_ALREADY_APPLIED)


class JobExpiredError(TerminalBotError):
    """Job requisition is closed or no longer accepting applications."""
    def __init__(self, message: str = "Job requisition is no longer accepting applications."):
        super().__init__(message, BotErrorCategory.TERMINAL_JOB_EXPIRED)


class HITLRequiredError(BotAutomationError):
    """Bot encountered a CAPTCHA or novel field requiring human intervention."""
    def __init__(self, message: str, event_id: str, category: BotErrorCategory = BotErrorCategory.HITL_CAPTCHA_DETECTED):
        super().__init__(message, category)
        self.event_id = event_id


def classify_bot_error(
    error: Any,
    page_text: str = "",
    status_code: Optional[int] = None
) -> BotErrorCategory:
    """
    Intelligently analyzes exception details, page contents, and HTTP statuses
    to determine the root failure taxonomy.
    """
    err_str = str(error).lower() if error else ""
    text_low = page_text.lower() if page_text else ""
    combined = f"{err_str} {text_low}"

    # 1. HTTP Status Code Classifications
    if status_code:
        if status_code == 429:
            return BotErrorCategory.TRANSIENT_RATE_LIMIT
        if status_code in (502, 503, 504):
            return BotErrorCategory.TRANSIENT_SERVER_ERROR
        if status_code == 403:
            return BotErrorCategory.TERMINAL_BLOCKED_WAF
        if status_code == 404:
            return BotErrorCategory.TERMINAL_JOB_EXPIRED

    # 2. CAPTCHA / Anti-Bot Challenges
    if any(k in combined for k in [
        "captcha", "recaptcha", "hcaptcha", "turnstile", "security check",
        "verify you are human", "cf-turnstile", "arkoselabs"
    ]):
        return BotErrorCategory.HITL_CAPTCHA_DETECTED

    # 3. Already Applied
    if any(k in combined for k in [
        "already applied", "already submitted an application",
        "duplicate application", "you have already applied"
    ]):
        return BotErrorCategory.TERMINAL_ALREADY_APPLIED

    # 4. Job Expired / Closed
    if any(k in combined for k in [
        "no longer accepting applications", "job posting has closed",
        "job is closed", "position has been filled", "expired job",
        "requisition closed", "this job is no longer available"
    ]):
        return BotErrorCategory.TERMINAL_JOB_EXPIRED

    # 5. Authentication / Login Required
    if any(k in combined for k in [
        "sign in to apply", "log in to continue", "create an account to apply",
        "sso login required", "enter password"
    ]):
        return BotErrorCategory.TERMINAL_AUTH_REQUIRED

    # 6. WAF / Bot Blocking
    if any(k in combined for k in [
        "cloudflare ray id", "access denied", "error 1020",
        "blocked by perimeterx", "akamai bot manager", "datadome"
    ]):
        return BotErrorCategory.TERMINAL_BLOCKED_WAF

    # 7. Form Validation Constraint Failures
    if any(k in combined for k in [
        "invalid input", "required field", "validation error",
        "please fill out this field", "field cannot be blank"
    ]):
        return BotErrorCategory.TERMINAL_FORM_VALIDATION

    # 8. Rate Limiting
    if any(k in combined for k in [
        "rate limit", "too many requests", "throttle"
    ]):
        return BotErrorCategory.TRANSIENT_RATE_LIMIT

    # 9. Timeouts (Transient)
    if any(k in combined for k in [
        "timeout", "timed out", "navigation timeout", "exceeded timeout"
    ]):
        return BotErrorCategory.TRANSIENT_TIMEOUT

    # 10. Network Blips (Transient)
    if any(k in combined for k in [
        "connection reset", "econnreset", "econnrefused", "getaddrinfo",
        "net::err", "socket closed", "dns"
    ]):
        return BotErrorCategory.TRANSIENT_NETWORK

    # 11. Server Errors (Transient)
    if any(k in combined for k in [
        "bad gateway", "service unavailable", "gateway timeout", "internal server error"
    ]):
        return BotErrorCategory.TRANSIENT_SERVER_ERROR

    return BotErrorCategory.UNKNOWN


def calculate_backoff_delay(
    attempt: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True
) -> float:
    """
    Calculates exponential backoff delay with decorrelated jitter.
    Attempt is 1-indexed (attempt=1 -> base_delay).
    """
    if attempt <= 0:
        attempt = 1
    exp_delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
    if jitter:
        # Full jitter: random uniform between 0.5 * delay and 1.2 * delay
        jitter_mult = random.uniform(0.5, 1.2)
        return min(max_delay, max(0.2, exp_delay * jitter_mult))
    return exp_delay
