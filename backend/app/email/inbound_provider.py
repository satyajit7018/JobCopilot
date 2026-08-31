"""
JobCopilot - Inbound Email Radar & Multi-Tenant Webhook Provider
Normalizes incoming webhook payloads from Postmark, SendGrid, Mailgun, and custom forwarders.
Resolves tenant isolation keys via subaddress routing (e.g. inbound+usr_123@jobcopilot.app).
"""

import re
import hmac
import hashlib
import logging
from typing import Dict, Any, Optional, Tuple
from app.core.settings import settings

logger = logging.getLogger("jobcopilot.email.inbound")

_SUBADDRESS_REGEX = re.compile(r'^[^+]+(?:\+([a-zA-Z0-9_\-]+))?@')


class InboundEmailProvider:
    """Parses and verifies inbound recruiter emails with automatic tenant attribution."""

    @classmethod
    def verify_webhook_signature(cls, payload_bytes: bytes, signature_header: Optional[str]) -> bool:
        """Verifies HMAC-SHA256 signature if secret is configured in production."""
        secret = settings.INBOUND_EMAIL_WEBHOOK_SECRET
        if not secret:
            return True  # Open in development if unconfigured

        if not signature_header:
            return False

        expected = hmac.new(secret.encode('utf-8'), payload_bytes, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature_header.strip())

    @classmethod
    def extract_tenant_user_id(cls, recipient_email: str, fallback_header: Optional[str] = None) -> str:
        """
        Extracts user_id from subaddress (e.g. radar+usr_9f43ab@jobcopilot.app -> usr_9f43ab)
        or header fallback.
        """
        if fallback_header:
            return fallback_header.strip()

        if recipient_email:
            match = _SUBADDRESS_REGEX.match(recipient_email.strip())
            if match and match.group(1):
                return match.group(1)

        return "default"

    @classmethod
    def parse_webhook_payload(cls, raw_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Normalizes generic, Postmark, and SendGrid webhook payload shapes.
        Returns standardized dict: {sender, recipient, subject, body_text, body_html, user_id}
        """
        # 1. Standard JobCopilot Payload
        if "sender" in raw_payload and "subject" in raw_payload:
            sender = raw_payload.get("sender", "")
            recipient = raw_payload.get("recipient", "")
            subject = raw_payload.get("subject", "")
            body_text = raw_payload.get("body_text") or raw_payload.get("body", "")
            body_html = raw_payload.get("body_html", "")
            user_id = raw_payload.get("user_id") or cls.extract_tenant_user_id(recipient)
            return {
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html or body_text,
                "user_id": user_id
            }

        # 2. Postmark Inbound Webhook Format
        if "From" in raw_payload and "Subject" in raw_payload:
            sender = raw_payload.get("FromFull", {}).get("Email") or raw_payload.get("From", "")
            recipient = raw_payload.get("ToFull", [{}])[0].get("Email") if raw_payload.get("ToFull") else raw_payload.get("To", "")
            subject = raw_payload.get("Subject", "")
            body_text = raw_payload.get("TextBody", "")
            body_html = raw_payload.get("HtmlBody", "")
            user_id = cls.extract_tenant_user_id(recipient)
            return {
                "sender": sender,
                "recipient": recipient,
                "subject": subject,
                "body_text": body_text,
                "body_html": body_html or body_text,
                "user_id": user_id
            }

        # 3. Fallback Generic
        sender = raw_payload.get("from", "recruiter@unknown.com")
        recipient = raw_payload.get("to", "radar+default@jobcopilot.app")
        subject = raw_payload.get("subject", "Recruiter Message")
        body_text = raw_payload.get("text", "")
        body_html = raw_payload.get("html", "")
        user_id = cls.extract_tenant_user_id(recipient)

        return {
            "sender": sender,
            "recipient": recipient,
            "subject": subject,
            "body_text": body_text,
            "body_html": body_html or body_text,
            "user_id": user_id
        }
