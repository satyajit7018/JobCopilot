"""
JobCopilot - Web Security Header Tests
The API's SecurityHeadersMiddleware and the frontend's nginx snippet
(frontend/security-headers.conf) must agree on the Content-Security-Policy.
(The legacy UI's PWA manifest, service worker and icon checks were removed with that UI.)
"""

import re
from pathlib import Path

from fastapi.testclient import TestClient

NGINX_HEADERS = Path(__file__).resolve().parents[2] / "frontend" / "security-headers.conf"


def _directive(csp: str, name: str) -> str:
    return next(p.strip() for p in csp.split(";") if p.strip().startswith(name))


def test_api_security_headers(client: TestClient):
    """Every API response carries the CSP and hardening headers."""
    res = client.get("/api/health")
    csp = res.headers.get("content-security-policy", "")
    assert "worker-src 'self'" in csp
    # script-src is 'self' plus Google Identity Services (Sign in with Google), and nothing else.
    script_directive = _directive(csp, "script-src")
    assert script_directive == "script-src 'self' https://accounts.google.com"
    assert "'unsafe-inline'" not in script_directive
    assert res.headers.get("x-frame-options") == "DENY"
    assert res.headers.get("x-content-type-options") == "nosniff"
    assert "microphone=(self)" in res.headers.get("permissions-policy", "")


def test_frontend_csp_matches_api(client: TestClient):
    """The page CSP served by nginx allows exactly the same scripts as the API's."""
    conf = NGINX_HEADERS.read_text(encoding="utf-8")
    match = re.search(r'add_header Content-Security-Policy "([^"]+)" always;', conf)
    assert match, "frontend/security-headers.conf must set a Content-Security-Policy"
    page_csp = match.group(1)

    api_csp = client.get("/api/health").headers["content-security-policy"]
    assert _directive(page_csp, "script-src") == _directive(api_csp, "script-src")
    assert "frame-ancestors 'none'" in page_csp
    assert "object-src 'none'" in page_csp
