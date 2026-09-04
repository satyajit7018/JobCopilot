"""
JobCopilot - Multi-Provider CAPTCHA & Bot Challenge Detector
Inspects Playwright pages and DOM snapshots to detect anti-bot challenges
(reCAPTCHA, hCaptcha, Turnstile, Arkose Labs) before forms fail silently.
"""

from typing import Optional, Dict, Any

# Common anti-bot challenge selector signatures
CAPTCHA_SIGNATURES = [
    {
        "provider": "recaptcha",
        "selectors": [
            "iframe[src*='recaptcha']",
            "iframe[src*='google.com/recaptcha']",
            ".g-recaptcha",
            "#recaptcha",
            "textarea[name='g-recaptcha-response']"
        ],
        "description": "Google reCAPTCHA challenge detected."
    },
    {
        "provider": "hcaptcha",
        "selectors": [
            "iframe[src*='hcaptcha']",
            "iframe[src*='hcaptcha.com']",
            ".h-captcha",
            "#h-captcha",
            "textarea[name='h-captcha-response']"
        ],
        "description": "hCaptcha challenge detected."
    },
    {
        "provider": "turnstile",
        "selectors": [
            "iframe[src*='challenges.cloudflare.com']",
            "iframe[src*='turnstile']",
            ".cf-turnstile",
            "input[name='cf-turnstile-response']"
        ],
        "description": "Cloudflare Turnstile challenge detected."
    },
    {
        "provider": "arkose",
        "selectors": [
            "iframe[src*='arkoselabs']",
            "iframe[src*='funcaptcha']",
            "#fc-iframe-wrap",
            "#arkose"
        ],
        "description": "Arkose Labs / FunCaptcha challenge detected."
    }
]

TEXT_CHALLENGE_KEYWORDS = [
    "please verify you are a human",
    "complete security check",
    "verify you are not a robot",
    "solve this puzzle to verify",
    "prove you are human",
    "security verification required"
]


def detect_captcha_in_html(html_str: str) -> Optional[Dict[str, Any]]:
    """
    Synchronous heuristic check for CAPTCHA patterns within HTML strings or DOM snapshots.
    """
    if not html_str:
        return None
    html_low = html_str.lower()

    for sig in CAPTCHA_SIGNATURES:
        for sel in sig["selectors"]:
            tag = sel.replace("iframe[src*='", "").replace("']", "").replace(".", "").replace("#", "")
            if tag in html_low:
                return {
                    "detected": True,
                    "provider": sig["provider"],
                    "selector": sel,
                    "description": sig["description"]
                }

    for phrase in TEXT_CHALLENGE_KEYWORDS:
        if phrase in html_low:
            return {
                "detected": True,
                "provider": "generic_challenge",
                "selector": "body",
                "description": f"Textual human challenge detected: '{phrase}'"
            }

    return None


async def detect_captcha(page: Any) -> Optional[Dict[str, Any]]:
    """
    Asynchronously queries the active Playwright page for interactive CAPTCHA widgets.
    """
    if not page or not hasattr(page, "query_selector"):
        return None

    try:
        for sig in CAPTCHA_SIGNATURES:
            for sel in sig["selectors"]:
                el = await page.query_selector(sel)
                if el:
                    # Verify element is visible or attached
                    try:
                        visible = await el.is_visible()
                    except Exception:
                        visible = True
                    if visible:
                        return {
                            "detected": True,
                            "provider": sig["provider"],
                            "selector": sel,
                            "description": sig["description"]
                        }

        # Check textual indicators in page content
        content = await page.content()
        return detect_captcha_in_html(content)
    except Exception:
        return None
