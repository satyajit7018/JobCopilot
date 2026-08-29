"""
JobCopilot - Privacy-First Inbound Email Parser & Tracking Pixel Stripper
Strips tracking pixels, web beacons, and surveillance telemetry from recruiter
emails before parsing plain text and scheduling links.
"""

import re
import html
from typing import Tuple, Dict, Any, Optional


class EmailParser:
    """Sanitizes incoming recruiter emails and strips tracking surveillance."""

    TRACKING_DOMAINS_REGEX = re.compile(
        r'https?://[^\s<>"]*(?:mandrillapp\.com|sendgrid\.net|mailgun\.org|hubspotlinks\.com|mixmax\.com|yesware\.com|streak\.com|superhuman\.com|mailtrack\.io)[^\s<>"]*',
        re.IGNORECASE
    )

    PIXEL_IMG_REGEX = re.compile(
        r'<img[^>]*(?:width=[\'"]?[01][\'"]?|height=[\'"]?[01][\'"]?|style=[\'"][^\'"]*(?:display:\s*none|visibility:\s*hidden|width:\s*[01]px|height:\s*[01]px)[^\'"]*)[^>]*>',
        re.IGNORECASE
    )

    @classmethod
    def strip_tracking_pixels(cls, html_content: str) -> Tuple[str, bool]:
        """
        Removes 1x1 tracking pixels, hidden beacons, and tracker redirect URLs.
        Returns (sanitized_html, has_tracking_pixels).
        """
        if not html_content:
            return "", False

        has_pixels = False

        # Check for tracking pixel images
        if cls.PIXEL_IMG_REGEX.search(html_content):
            has_pixels = True
            html_content = cls.PIXEL_IMG_REGEX.sub('', html_content)

        # Check for known spy tracker domains
        if cls.TRACKING_DOMAINS_REGEX.search(html_content):
            has_pixels = True
            html_content = cls.TRACKING_DOMAINS_REGEX.sub('', html_content)

        return html_content, has_pixels

    @classmethod
    def html_to_clean_text(cls, html_content: str) -> str:
        """Converts HTML email body into clean plain text while preserving hyperlinks."""
        if not html_content:
            return ""

        # Preserve hrefs: <a href="url">text</a> -> text (url)
        def replace_link(match):
            href = match.group(1)
            inner_text = re.sub(r'<[^>]+>', '', match.group(2)).strip()
            if not inner_text:
                return href
            if href.lower() in inner_text.lower():
                return inner_text
            return f"{inner_text} ({href})"

        preserved = re.sub(r'<a\s+[^>]*href=[\'"]([^\'"]+)[\'"][^>]*>(.*?)</a>', replace_link, html_content, flags=re.DOTALL | re.IGNORECASE)

        # Strip scripts and styles
        cleaned = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', preserved, flags=re.DOTALL | re.IGNORECASE)
        # Strip remaining HTML tags
        cleaned = re.sub(r'<[^>]+>', ' ', cleaned)
        # Unescape HTML entities
        cleaned = html.unescape(cleaned)
        # Normalize whitespace
        cleaned = re.sub(r'[ \t]+', ' ', cleaned)
        cleaned = re.sub(r'\n\s*\n', '\n\n', cleaned).strip()
        return cleaned

    @classmethod
    def parse_raw_email(cls, sender: str, recipient: str, subject: str, body_html: str, body_text: Optional[str] = None) -> Dict[str, Any]:
        """Parses raw email payload with privacy stripping."""
        sanitized_html, has_pixels = cls.strip_tracking_pixels(body_html or "")
        
        final_text = body_text
        if not final_text or len(final_text.strip()) < 10:
            final_text = cls.html_to_clean_text(sanitized_html)

        return {
            "sender": sender.strip(),
            "recipient": recipient.strip(),
            "subject": subject.strip(),
            "body_text": final_text,
            "has_tracking_pixels": has_pixels
        }
