"""
JobCopilot - Milestone 3 End-to-End Test Suite
Tests Chromium CSS Paged Media PDF Resume Engine, Keyword Alignment,
Anti-AI Cover Letter Generator, and Triple-Threat Outreach Generator.
"""

import sys
import uuid
from pathlib import Path
import pytest
from pypdf import PdfReader

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent.resolve()))

from app.core.models import CandidateProfile, CategorizedSkills, Project, Education, WorkExperience
from app.core.database import DatabaseManager
from app.core.resume_compiler import ResumeCompiler
from app.core.resume_tailor import ResumeTailor
from app.core.cover_letter import CoverLetterGenerator
from app.core.outreach_generator import OutreachGenerator


class TestMilestone3:

    @pytest.fixture(autouse=True)
    def setup_candidate(self, tmp_path):
        self.db_path = tmp_path / "test_m3.db"
        self.db = DatabaseManager(self.db_path)
        self.profile = CandidateProfile(
            full_name="Satyajit Nayak",
            email="scorpionsatyajit@gmail.com",
            phone="+91 7008053476",
            location="Bangalore, India",
            linkedin_url="https://linkedin.com/in/satyajit-nayak",
            github_url="https://github.com/satyajit7018",
            skills=["SQL", "Python", "Docker", "FastAPI", "PyTorch", "PostgreSQL"],
            categorized_skills=CategorizedSkills(
                languages=["SQL", "Python"],
                frameworks=["FastAPI", "PyTorch"],
                cloud_devops=["Docker", "AWS"],
                databases=["PostgreSQL"]
            ),
            experience=[
                WorkExperience(
                    company="AI Research Lab",
                    title="Machine Learning Engineer Intern",
                    start_date="Jan 2024",
                    end_date="Present",
                    highlights=[
                        "Engineered PyTorch neural architectures for medical image segmentation.",
                        "Optimized FastAPI endpoints achieving <40ms response latency."
                    ],
                    tech_stack=["Python", "PyTorch", "FastAPI"]
                )
            ],
            projects=[
                Project(
                    name="Medical Diagnostic AI",
                    description="Deep learning multimodal classification model.",
                    technologies=["PyTorch", "FastAPI", "Docker"],
                    metrics="96.19% accuracy on test cohort"
                ),
                Project(
                    name="SQL Data Lakehouse",
                    description="Columnar data pipeline.",
                    technologies=["SQL", "PostgreSQL"]
                )
            ],
            education=[
                Education(degree="B.Tech Computer Science", institution="VIT", graduation_year="2025")
            ]
        )

    # 1. Test HTML Generation & Chromium CSS Paged Media PDF Compilation
    @pytest.mark.asyncio
    async def test_pdf_resume_compilation(self, tmp_path):
        html_doc = ResumeCompiler.generate_resume_html(self.profile)
        assert "SATYAJIT NAYAK" in html_doc or "Satyajit Nayak" in html_doc
        assert "scorpionsatyajit@gmail.com" in html_doc

        pdf_path = tmp_path / "test_out.pdf"
        await ResumeCompiler.compile_to_pdf(html_doc, pdf_path)
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 1000

        # Validate with pypdf
        reader = PdfReader(str(pdf_path))
        text = reader.pages[0].extract_text()
        assert "SATYAJIT NAYAK" in text
        assert "PyTorch" in text
        assert "96.19%" in text

    # 2. Test Keyword Alignment & Project Reordering
    def test_resume_tailoring_reorder(self):
        ai_jd = "Seeking a Python AI engineer with PyTorch and Docker experience."
        tailored, matched = ResumeTailor.tailor_profile_for_job(self.profile, "AI Engineer", ai_jd)

        # PyTorch & Docker matched
        assert "PyTorch" in matched
        assert "Docker" in matched

        # Projects reordered so Medical Diagnostic AI is first
        assert tailored.projects[0].name == "Medical Diagnostic AI"

        # Languages: Python should be promoted to the front over SQL
        assert tailored.categorized_skills.languages[0] == "Python"

    # 3. Test Human-Tone Cover Letter & Anti-AI Filter
    def test_cover_letter_and_anti_ai(self):
        letter = CoverLetterGenerator.generate_cover_letter(
            profile=self.profile,
            company_name="Perplexity",
            job_title="AI Systems Engineer"
        )
        assert "Perplexity" in letter
        assert "AI Systems Engineer" in letter
        assert "96.19% accuracy" in letter
        assert "github.com/satyajit7018" in letter

        # Check absence of AI buzzwords
        for bad_word in CoverLetterGenerator.FORBIDDEN_AI_CLICHES:
            assert bad_word.lower() not in letter.lower(), f"Found cliché: {bad_word}"

    # 4. Test Triple-Threat Outreach Generation (LinkedIn + Cold Email)
    def test_triple_threat_outreach(self):
        job_id = f"job_test_{uuid.uuid4().hex[:6]}"
        pkg = OutreachGenerator.create_triple_threat_package(
            profile=self.profile,
            job_id=job_id,
            company_name="Perplexity",
            job_title="AI Systems Engineer",
            manager_name="Aravind Srinivas"
        )

        li_note = pkg["linkedin_note"]
        email_obj = pkg["cold_email"]

        # Enforce LinkedIn 280-char limit
        assert len(li_note) <= 280
        assert "Aravind" in li_note

        # Verify cold email
        assert "AI Systems Engineer" in email_obj["subject"]
        assert "Perplexity" in email_obj["body"]
        assert "Medical Diagnostic AI" in email_obj["body"]
