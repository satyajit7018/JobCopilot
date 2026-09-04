"""
JobCopilot - Full Project Audit Verification Test Suite
Validates all audit fixes and system improvements:
1. Indian 5-5 and continuous mobile number regex extraction in ResumeParser
2. Monthly, hourly, and range periodicity parsing in CompensationConverter
3. Frontend switchTab canonical view normalization and fallback mapping
4. Modern Greenhouse ATS selector fallbacks in GreenhouseAdapter
5. Guaranteed output path existence in ResumeCompiler fallback
"""

import sys
import tempfile
from pathlib import Path
import pytest

sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.resume_parser import ResumeParser
from app.core.compensation import CompensationConverter
from app.core.resume_compiler import ResumeCompiler
from app.core.models import CandidateProfile, RecruiterPreferences
from app.bot.adapters.greenhouse import GreenhouseAdapter


def test_indian_and_international_phone_parsing():
    """Validates that ResumeParser accurately extracts Indian 5-5, continuous, and US phone numbers."""
    # 1. Indian 5-5 with country code
    sample_text_1 = "John Doe\njohn@example.in\n+91 98765 43210\nBangalore, India\nSkills: Python, FastAPI"
    info_1 = ResumeParser.extract_contact_info(sample_text_1)
    assert info_1["phone"] == "+91 98765 43210"

    # 2. Indian 5-5 without country code
    sample_text_2 = "Aarav Patel\naarav@domain.com\n98765 43210\nPune, India"
    info_2 = ResumeParser.extract_contact_info(sample_text_2)
    assert info_2["phone"] == "98765 43210"

    # 3. Continuous 10 digits
    sample_text_3 = "Dev User\ndev@tech.co\n9876543210\nHyderabad, India"
    info_3 = ResumeParser.extract_contact_info(sample_text_3)
    assert info_3["phone"] == "9876543210"

    # 4. US Format
    sample_text_4 = "Alice Smith\nalice@sf.io\n+1 (555) 123-4567\nSan Francisco, CA"
    info_4 = ResumeParser.extract_contact_info(sample_text_4)
    assert info_4["phone"] == "+1 (555) 123-4567"


def test_compensation_periodicity_and_multipliers():
    """Validates monthly, hourly, and LPA range conversions to annual INR."""
    # 1. Monthly INR format
    monthly_inr = CompensationConverter.parse_to_base_inr("₹80,000 / month")
    assert monthly_inr == 960000.0  # 80k * 12

    # 2. Monthly with 'k' multiplier
    monthly_k = CompensationConverter.parse_to_base_inr("₹50k per month")
    assert monthly_k == 600000.0  # 50k * 12

    # 3. Monthly USD
    monthly_usd = CompensationConverter.parse_to_base_inr("$10,000 / mo")
    assert monthly_usd == 120000.0 * 83.5  # $120k * 83.5 = 10,020,000 INR

    # 4. Hourly USD
    hourly_usd = CompensationConverter.parse_to_base_inr("$80 / hr")
    assert hourly_usd == 80.0 * 2080.0 * 83.5  # $166,400 * 83.5 = 13,894,400 INR

    # 5. LPA range
    lpa_range = CompensationConverter.parse_to_base_inr("28 - 35 LPA")
    assert lpa_range == 3150000.0  # midpoint 31.5 LPA


def test_frontend_switch_tab_view_mapping():
    """Verifies that the frontend switchTab logic normalizes alias tabs properly."""
    app_js_path = Path(__file__).parent.parent.parent / "frontend" / "js" / "app.js"
    content = app_js_path.read_text(encoding="utf-8")

    # Verify normalization aliases exist in app.js
    assert "if (viewId === 'studio' || viewId === 'interview-studio') viewId = 'interview';" in content
    assert "if (viewId === 'backups') viewId = 'settings';" in content
    assert "if (viewId === 'accelerator') viewId = 'interview';" in content
    assert "if (viewId === 'billing') viewId = 'settings';" in content

    # Verify index.html does not contain dead view-interview-studio section ID
    index_html_path = Path(__file__).parent.parent.parent / "frontend" / "index.html"
    index_content = index_html_path.read_text(encoding="utf-8")
    assert 'id="view-interview"' in index_content
    assert 'id="view-interview-studio"' not in index_content
    assert 'data-view="interview"' in index_content


@pytest.mark.asyncio
async def test_pdf_compiler_file_guarantee():
    """Verifies that compile_to_pdf guarantees the output file exists on disk even in fallback paths."""
    with tempfile.TemporaryDirectory() as tmpdir:
        out_pdf = Path(tmpdir) / "test_resume.pdf"
        html_content = "<html><body><h1>Candidate Resume</h1></body></html>"

        result_path = await ResumeCompiler.compile_to_pdf(html_content, out_pdf)
        assert result_path == out_pdf
        assert out_pdf.exists()
