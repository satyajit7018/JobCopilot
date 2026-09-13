"""
JobCopilot - Legal Routes Test Suite
Validates that /legal/terms and /legal/privacy return HTTP 200 with rendered HTML content.
"""

import pytest
from starlette.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)

def test_legal_terms_endpoint(client):
    response = client.get("/legal/terms")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Terms of Service" in response.text
    assert "JobCopilot" in response.text

def test_legal_privacy_endpoint(client):
    response = client.get("/legal/privacy")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Privacy Policy" in response.text
    assert "JobCopilot" in response.text
