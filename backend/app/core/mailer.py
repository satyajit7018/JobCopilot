"""
JobCopilot - Transactional Email & SMTP Service
Handles password reset links, email verification tokens, and candidate alert dispatches
with safe asynchronous fallback for development environments.
"""

import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.core.settings import settings

logger = logging.getLogger("jobcopilot.mailer")


class EmailService:
    """Delivers transactional emails over SMTP with safe development fallbacks."""

    @classmethod
    def send_email(cls, to_email: str, subject: str, body_text: str, body_html: Optional[str] = None) -> bool:
        """Sends an email via configured SMTP host or logs to development console."""
        # Development / Headless Fallback
        if settings.ENV.lower() != "production" and (not settings.SMTP_USER or settings.SMTP_HOST == "localhost"):
            logger.info(
                f"[DEV MAILER] To: {to_email} | Subject: {subject}\n"
                f"--- Message Body ---\n{body_text}\n--------------------"
            )
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = settings.SMTP_FROM_EMAIL
            msg["To"] = to_email

            part1 = MIMEText(body_text, "plain")
            msg.attach(part1)

            if body_html:
                part2 = MIMEText(body_html, "html")
                msg.attach(part2)

            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10.0) as server:
                if settings.SMTP_TLS:
                    server.starttls()
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(settings.SMTP_FROM_EMAIL, [to_email], msg.as_string())

            logger.info(f"Successfully dispatched transactional email to {to_email}")
            return True
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False

    @classmethod
    def send_verification_email(cls, to_email: str, token: str) -> bool:
        """Sends email verification link."""
        verify_url = f"http://localhost:{settings.FRONTEND_PORT}/#verify?token={token}"
        subject = "Verify your JobCopilot Account"
        body = (
            f"Welcome to JobCopilot!\n\n"
            f"Please verify your email address by clicking the link below:\n"
            f"{verify_url}\n\n"
            f"This link will expire in 24 hours.\n\n"
            f"Best regards,\nThe JobCopilot Team"
        )
        return cls.send_email(to_email, subject, body)

    @classmethod
    def send_password_reset_email(cls, to_email: str, token: str) -> bool:
        """Sends password reset link."""
        reset_url = f"http://localhost:{settings.FRONTEND_PORT}/#reset-password?token={token}"
        subject = "JobCopilot Password Reset Request"
        body = (
            f"Hello,\n\n"
            f"We received a request to reset your JobCopilot password.\n"
            f"You can reset your password using the link below:\n"
            f"{reset_url}\n\n"
            f"This link will expire in 15 minutes. If you did not make this request, please ignore this email.\n\n"
            f"Best regards,\nThe JobCopilot Security Team"
        )
        return cls.send_email(to_email, subject, body)


mailer = EmailService()
