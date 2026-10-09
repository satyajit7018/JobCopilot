"""
JobCopilot - Enhanced Universal Resume Parser
Robustly extracts structured candidate profiles from PDF, DOCX, and raw text
with section segmentation, date parsing, and categorized skill taxonomy.
"""

import asyncio
import logging
import re
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

try:
    from pypdf import PdfReader  # type: ignore
    HAS_PYPDF = True
except ImportError:
    PdfReader = None  # type: ignore
    HAS_PYPDF = False

try:
    import docx  # type: ignore
    HAS_DOCX = True
except ImportError:
    HAS_DOCX = False

from app.core.models import (
    CandidateProfile,
    CategorizedSkills,
    Education,
    Project,
    RecruiterPreferences,
    WorkExperience,
)


class ResumeParser:
    """Universal parser for PDF, DOCX, and text resumes into structured CandidateProfile."""

    SKILL_TAXONOMY = {
        "languages": [
            "Python", "JavaScript", "TypeScript", "C++", "C#", "Java", "Go", "Golang",
            "Rust", "Ruby", "PHP", "Swift", "Kotlin", "SQL", "HTML", "CSS", "Bash", "R", "Scala"
        ],
        "frameworks": [
            "React", "React.js", "Vue", "Vue.js", "Next.js", "Node.js", "FastAPI", "Django",
            "Flask", "Express.js", "Spring Boot", "PyTorch", "TensorFlow", "Keras", "Scikit-Learn",
            "TailwindCSS", "Redux", "GraphQL", "ASP.NET", "Angular"
        ],
        "cloud_devops": [
            "AWS", "Amazon Web Services", "GCP", "Google Cloud", "Azure", "Docker", "Kubernetes",
            "Terraform", "CI/CD", "GitHub Actions", "GitLab CI", "Linux", "Nginx", "Ansible", "Helm"
        ],
        "databases": [
            "PostgreSQL", "Postgres", "MySQL", "MongoDB", "Redis", "SQLite", "Elasticsearch",
            "Qdrant", "ChromaDB", "DynamoDB", "Cassandra", "Snowflake", "BigQuery", "Neo4j"
        ],
        "tools_libraries": [
            "Git", "GitHub", "Jira", "Postman", "OpenCV", "LangChain", "LlamaIndex",
            "Playwright", "Selenium", "Pandas", "NumPy", "Apache Kafka", "Kafka", "RabbitMQ", "Celery"
        ]
    }

    @classmethod
    def extract_text_from_pdf(cls, pdf_path: str) -> str:
        """Extracts plain text from all pages of a PDF."""
        if not HAS_PYPDF or PdfReader is None:
            try:
                with open(pdf_path, encoding="utf-8", errors="ignore") as f:
                    return f.read()
            except Exception:
                return ""
        text = ""
        reader = PdfReader(pdf_path)
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text

    @classmethod
    def extract_text_from_docx(cls, docx_path: str) -> str:
        """Extracts plain text from a DOCX file."""
        if not HAS_DOCX:
            return ""
        doc = docx.Document(docx_path)
        return "\n".join([p.text for p in doc.paragraphs if p.text])

    @classmethod
    def extract_raw_text(cls, source_path_or_text: str) -> str:
        """Extracts raw text from file path (PDF/DOCX) or returns raw string."""
        if "\n" not in source_path_or_text and len(source_path_or_text) < 260:
            try:
                path = Path(source_path_or_text)
                if path.exists() and path.is_file():
                    ext = path.suffix.lower()
                    if ext == ".pdf":
                        return cls.extract_text_from_pdf(str(path))
                    elif ext in [".docx", ".doc"]:
                        return cls.extract_text_from_docx(str(path))
                    else:
                        with open(path, encoding="utf-8", errors="ignore") as f:
                            return f.read()
            except Exception:
                logger.debug("resume_parser: failed reading resume file path, treating as raw text", exc_info=True)
                pass
        return source_path_or_text

    @classmethod
    def extract_contact_info(cls, text: str) -> Dict[str, Optional[str]]:
        """Extracts email, phone, LinkedIn, GitHub, and Portfolio URLs."""
        # Email
        email_match = re.search(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', text)
        email = email_match.group(0) if email_match else "candidate@example.com"

        # Phone (International, local, and Indian 5-5 grouped formats)
        phone_match = re.search(
            r'(?:\+?\d{1,3}[-.\s]?)?(?:(?:\(?\d{3,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{4})|(?:\d{5}[-.\s]?\d{5}))',
            text
        )
        phone = phone_match.group(0) if phone_match else "+91 0000000000"

        # LinkedIn URL
        linkedin_match = re.search(r'https?://(?:www\.)?linkedin\.com/in/[A-Za-z0-9\-_]+', text)
        linkedin_url = linkedin_match.group(0) if linkedin_match else None

        # GitHub URL
        github_match = re.search(r'https?://(?:www\.)?github\.com/[A-Za-z0-9\-_]+', text)
        github_url = github_match.group(0) if github_match else None

        # Portfolio URL
        portfolio_match = re.search(r'https?://(?:www\.)?(?!linkedin|github)[A-Za-z0-9\-_.]+\.[a-z]{2,}(?:/[^\s]*)?', text)
        portfolio_url = portfolio_match.group(0) if portfolio_match else None

        # Location heuristic
        location = ""
        # "based in X" first: the generic pattern would swallow the name before it.
        loc_patterns = [
            r'\bbased in\s+([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?,\s*[A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+)?)\b',
            r'\b([A-Z][a-zA-Z]+(?: [A-Z][a-zA-Z]+){0,2},\s*(?:[A-Z]{2}|India|USA|United States|UK|Canada|Germany|California|Texas|Washington|Karnataka|Maharashtra|Telangana|Tamil Nadu|Bangalore|Bengaluru|Hyderabad|Delhi|Mumbai|Pune|Gurgaon|Noida)(?:,\s*India)?)\b',
        ]
        for pat in loc_patterns:
            m = re.search(pat, text)
            if m:
                location = m.group(1).strip()
                break

        # Name extraction (usually top line)
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        full_name = "Candidate Name"
        for line in lines[:5]:
            # If line looks like a valid name (2-4 words, no email or url)
            if 2 <= len(line.split()) <= 4 and not re.search(r'[@:/|0-9]', line) and len(line) < 40:
                full_name = line.strip()
                break

        # Fallback for unstructured inline names
        if full_name == "Candidate Name":
            name_inline = re.search(r'(?:^|[.\n])\s*(?:name:?|i am)?\s*([A-Z][a-z]+\s+[A-Z][a-z]+)\s+based in', text, re.IGNORECASE)
            if name_inline:
                full_name = name_inline.group(1).strip()

        return {
            "email": email,
            "phone": phone,
            "linkedin_url": linkedin_url,
            "github_url": github_url,
            "portfolio_url": portfolio_url,
            "location": location,
            "full_name": full_name
        }

    _SKILL_PATTERNS: Dict[str, Tuple[str, "re.Pattern[str]"]] = {}

    @classmethod
    def _skill_pattern(cls, skill: str) -> Tuple[str, "re.Pattern[str]"]:
        cached = cls._SKILL_PATTERNS.get(skill)
        if cached is None:
            needle = skill.lower()
            # Word boundary match
            cached = (needle, re.compile(r'(?<!\w)' + re.escape(needle) + r'(?!\w)'))
            cls._SKILL_PATTERNS[skill] = cached
        return cached

    @classmethod
    def categorize_skills(cls, text: str) -> Tuple[List[str], CategorizedSkills]:
        """Categorizes all matched technical skills into taxonomy buckets."""
        text_lower = text.lower()
        categorized = CategorizedSkills()
        all_skills = []
        seen = set()

        for category, skills in cls.SKILL_TAXONOMY.items():
            bucket = []
            for skill in skills:
                needle, pattern = cls._skill_pattern(skill)
                # Cheap substring test first: the word-boundary regex can only
                # match if the skill text appears at all. Discovery scores
                # thousands of job descriptions, so this matters.
                if needle in text_lower and pattern.search(text_lower):
                    bucket.append(skill)
                    if skill not in seen:
                        seen.add(skill)
                        all_skills.append(skill)
            setattr(categorized, category, bucket)

        return all_skills, categorized

    @classmethod
    def extract_summary(cls, text: str) -> str:
        """The resume's own summary/objective paragraph, if it has one."""
        for raw_heading in ("SUMMARY", "PROFESSIONAL SUMMARY", "OBJECTIVE", "PROFILE", "ABOUT"):
            m = re.search(rf"(?im)^\s*{raw_heading}\s*:?\s*$\n((?:.+\n?){{1,6}})", text)
            if m:
                para = []
                for line in m.group(1).split("\n"):
                    if not line.strip() or cls._section_of(line.strip()):
                        break
                    para.append(line.strip())
                summary = " ".join(para)
                # Drop salary/notice details people put in summaries; they have their own fields.
                summary = re.split(r"\s*\b(?:current ctc|expected ctc|expected:|notice period)\b", summary, flags=re.IGNORECASE)[0]
                return summary.strip()[:600]
        return ""

    @classmethod
    def extract_education(cls, text: str) -> List[Education]:
        """Degrees and schools as written; nothing is filled in when the resume doesn't say."""
        lines = cls._sections(text).get("education", [])
        entries: List[Education] = []
        degree = school = year = ""

        def flush():
            nonlocal degree, school, year
            if degree or school:
                entries.append(Education(degree=degree, institution=school, graduation_year=year or None))
            degree = school = year = ""

        for line in lines:
            if cls.BULLET.match(line) or line.lower().startswith(("gpa", "cgpa", "grade", "relevant")):
                continue
            pieces = [p.strip() for p in re.split(r"\s*[|•·]\s*|\s+[-–—]\s+|,\s+", line) if p.strip()]
            found_year = next((m.group(0) for m in re.finditer(r"(?:19|20)\d{2}", line)), "")
            is_school = any(cls.INSTITUTION_WORDS.search(p) for p in pieces)
            # A bare two-letter piece is a US state ("Cambridge, MA"), not a degree.
            degree_pieces = [p for p in pieces if cls.DEGREE_WORDS.search(p) and not cls.INSTITUTION_WORDS.search(p)
                             and not re.fullmatch(r"[A-Z]{2}", p)]
            is_degree = bool(degree_pieces)
            if is_school:
                if school:
                    flush()
                school = next(p for p in pieces if cls.INSTITUTION_WORDS.search(p))
            if is_degree:
                if degree:
                    flush()
                degree = degree_pieces[0]
                degree = re.sub(r"\s*,?\s*(?:19|20)\d{2}.*$", "", degree).strip()
            if found_year:
                year = found_year
            if degree and school and year:
                flush()
        flush()

        if not entries:
            # Prose: "graduated with B.Tech in 2018 from Delhi Technological University".
            m = re.search(
                r"\b(B\.?\s?Tech|M\.?\s?Tech|B\.?E|B\.?S\.?c?|M\.?S\.?c?|MBA|Ph\.?D|Bachelor[^,.]*?|Master[^,.]*?)"
                r"(?:\s+in\s+((?:19|20)\d{2}))?\s+(?:from|at)\s+([A-Z][\w.&' ]+?(?:University|Institute[\w ]*|College|School))",
                text,
            )
            if m:
                entries.append(Education(degree=m.group(1).strip(), institution=m.group(3).strip(), graduation_year=m.group(2)))
        return entries

    @classmethod
    def extract_skills(cls, text: str) -> List[str]:
        """Extracts unique technical skills from resume text."""
        all_skills, _ = cls.categorize_skills(text)
        return all_skills

    # --- Section-aware reading of experience, education and projects -------------------
    # Rule: read what the resume says; leave a field empty rather than invent it.

    SECTION_HEADERS = {
        "experience": ("EXPERIENCE", "WORK EXPERIENCE", "PROFESSIONAL EXPERIENCE", "EMPLOYMENT", "WORK HISTORY", "CAREER HISTORY"),
        "projects": ("PROJECTS", "PERSONAL PROJECTS", "KEY PROJECTS", "ACADEMIC PROJECTS", "SIDE PROJECTS"),
        "education": ("EDUCATION", "ACADEMIC BACKGROUND", "QUALIFICATIONS"),
        "other": ("SKILLS", "TECHNICAL SKILLS", "CERTIFICATIONS", "PUBLICATIONS", "SUMMARY", "PROFESSIONAL SUMMARY",
                  "OBJECTIVE", "AWARDS", "LANGUAGES", "INTERESTS", "ACHIEVEMENTS", "PROFILE", "CONTACT"),
    }
    _MONTH = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
    _DATE = rf"(?:{_MONTH}\s+|\d{{1,2}}/)?(?:19|20)\d{{2}}"
    DATE_RANGE = re.compile(rf"({_DATE})\s*(?:-|–|—|to|until)\s*({_DATE}|present|current|now|today|date)", re.IGNORECASE)
    TITLE_WORDS = re.compile(
        r"\b(engineer\w*|developer|intern|manager|lead|architect|scientist|analyst|consultant|designer|director|"
        r"sde|sre|programmer|specialist|head|vp|officer|administrator|researcher|founder|co-founder|associate|"
        r"technician|tester|devops)\b", re.IGNORECASE)
    INSTITUTION_WORDS = re.compile(r"\b(university|institute|college|school|academy|polytechnic|iit|nit|bits|iiit)\b", re.IGNORECASE)
    DEGREE_WORDS = re.compile(
        r"\b(bachelor|master|b\.?\s?tech|m\.?\s?tech|b\.?\s?e\b|m\.?\s?e\b|b\.?s\.?c?\b|m\.?s\.?c?\b|b\.?a\b|m\.?a\b|"
        r"mba|ph\.?\s?d|doctor|diploma|certificate|associate degree|bca|mca)", re.IGNORECASE)
    BULLET = re.compile(r"^[•\-\*–—▪●◦]\s*")

    @classmethod
    def _section_of(cls, line: str) -> Optional[str]:
        """Which section a heading line starts, if it is one ("EXPERIENCE", "Work History:")."""
        clean = re.sub(r"[^A-Za-z ]", "", line).strip().upper()
        if not clean or len(clean) > 40:
            return None
        for name, headers in cls.SECTION_HEADERS.items():
            if clean in headers:
                return name
        return None

    @classmethod
    def _sections(cls, text: str) -> Dict[str, List[str]]:
        sections: Dict[str, List[str]] = {}
        current: Optional[str] = None
        for raw in text.split("\n"):
            line = raw.strip()
            if not line:
                continue
            name = cls._section_of(line)
            if name:
                current = name
                sections.setdefault(name, [])
                continue
            if current:
                sections[current].append(line)
        return sections

    @classmethod
    def _looks_like_location(cls, part: str) -> bool:
        from app.core.match_scorer import MatchScorer
        p = part.strip()
        return bool(
            MatchScorer._regions(p)
            or re.fullmatch(r"(?i)remote|hybrid|on-?site", p)
            or re.fullmatch(r"[A-Z][a-zA-Z.]+(?: [A-Z][a-zA-Z.]+)*,\s*[A-Z]{2}", p)
        )

    @classmethod
    def _split_header(cls, line: str) -> List[str]:
        parts: List[str] = []
        for piece in re.split(r"\s*[|•·]\s*", line):
            if cls.TITLE_WORDS.search(piece):
                # "Senior Engineer, Acme - Pune" / "Engineer at Acme"
                parts.extend(p for p in re.split(r",\s+|\s+[-–—]\s+|\s+at\s+|\s+@\s+", piece) if p)
            else:
                parts.append(piece)
        return [p.strip(" ,;:-–—") for p in parts if p.strip(" ,;:-–—")]

    @classmethod
    def _parse_date(cls, value: str, end: bool = False) -> Optional[datetime]:
        v = value.strip().lower()
        if v in ("present", "current", "now", "today", "date"):
            return datetime.now()
        year = re.search(r"(19|20)\d{2}", v)
        if not year:
            return None
        month = 12 if end else 1
        m = re.match(r"([a-z]+)", v)
        if m:
            months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
            for i, name in enumerate(months):
                if m.group(1).startswith(name):
                    month = i + 1
                    break
        slash = re.match(r"(\d{1,2})/", v)
        if slash:
            month = max(1, min(12, int(slash.group(1))))
        return datetime(int(year.group(0)), month, 1)

    @classmethod
    def extract_experience(cls, text: str) -> List[WorkExperience]:
        lines = cls._sections(text).get("experience", [])
        entries: List[Dict[str, Any]] = []
        current: Optional[Dict[str, Any]] = None
        for line in lines:
            if cls.BULLET.match(line):
                if current is not None:
                    current["bullets"].append(cls.BULLET.sub("", line))
                continue
            if current is None or current["bullets"]:
                current = {"headers": [], "bullets": []}
                entries.append(current)
            current["headers"].append(line)

        experience: List[WorkExperience] = []
        for entry in entries:
            header = "\n".join(entry["headers"])
            start = end = ""
            rng = cls.DATE_RANGE.search(header)
            if rng:
                start, end = rng.group(1).strip(), rng.group(2).strip()
                if end.lower() in ("current", "now", "today", "date"):
                    end = "Present"
                elif end.lower() == "present":
                    end = "Present"
                header = header[:rng.start()] + header[rng.end():]
            parts = [p for line in header.split("\n") for p in cls._split_header(line)]
            title = next((p for p in parts if cls.TITLE_WORDS.search(p)), "")
            company = next((p for p in parts if p != title and not cls._looks_like_location(p)
                            and not re.fullmatch(r"[\d\s/-]+", p)), "")
            location = next((p for p in parts if p not in (title, company) and cls._looks_like_location(p)), None)
            if not (title or company):
                continue
            bullets = entry["bullets"]
            experience.append(WorkExperience(
                company=company,
                title=title,
                start_date=start,
                end_date=end,
                location=location,
                highlights=bullets[:8],
                tech_stack=[s for s in cls.extract_skills(" ".join(bullets))][:8],
            ))

        if not experience:
            # Prose resumes: "worked at PayTM as tech lead ... from 2019 to now".
            prose = re.search(
                r"\b(?:work(?:ed|ing)|employed)\s+(?:at|for)\s+([A-Z][\w&.\-]*(?:\s+[A-Z][\w&.\-]*)*)\s+as\s+(?:an?\s+)?([a-zA-Z][a-zA-Z /-]{2,40}?)"
                r"(?=\s+(?:building|working|doing|leading|from|since|where|and|,|\.)|[,.]|$)",
                text,
            )
            if prose:
                when = re.search(r"\b(?:from|since)\s+((?:19|20)\d{2})(?:\s+(?:to|until|-)\s+((?:19|20)\d{2}|now|present|today))?", text[prose.start():], re.IGNORECASE)
                end_value = (when.group(2) or "Present") if when else ""
                experience.append(WorkExperience(
                    company=prose.group(1).strip(),
                    title=prose.group(2).strip().title(),
                    start_date=when.group(1) if when else "",
                    end_date="Present" if end_value.lower() in ("now", "present", "today") else end_value,
                ))
        return experience

    @classmethod
    def extract_projects(cls, text: str) -> List[Project]:
        lines = cls._sections(text).get("projects", [])
        projects: List[Project] = []
        name: Optional[str] = None
        bullets: List[str] = []

        def flush():
            if name:
                desc = " ".join(bullets)
                projects.append(Project(name=name, description=desc[:300],
                                        technologies=cls.extract_skills(f"{name} {desc}")[:6]))

        for line in lines:
            if cls.BULLET.match(line):
                bullets.append(cls.BULLET.sub("", line))
                continue
            flush()
            name, bullets = None, []
            if ":" in line and not line.lower().startswith("http"):
                head, rest = line.split(":", 1)
                if 2 < len(head.strip()) < 70:
                    name, bullets = head.strip(), [rest.strip()]
                    continue
            name = re.split(r"\s+[|–—]\s+", line)[0].strip()[:80]
        flush()
        return projects

    @classmethod
    def extract_projects_and_experience(cls, text: str) -> Tuple[List[WorkExperience], List[Project]]:
        """Work experience and projects as written in the resume (nothing is made up)."""
        return cls.extract_experience(text), cls.extract_projects(text)

    @classmethod
    def calculate_estimated_yoe(cls, text: str, experience: Optional[List[WorkExperience]] = None) -> float:
        """Years of experience: what the resume states ("5+ years"), else the sum of its job date ranges."""
        stated = re.search(r"\b(\d{1,2})(?:\.\d)?\s*\+?\s*(?:years?|yrs?)\b(?:\s+of)?(?:\s+\w+){0,3}?\s+experience", text, re.IGNORECASE)
        if stated and 0 < int(stated.group(1)) <= 40:
            return float(stated.group(1))

        spans = []
        for job in experience if experience is not None else cls.extract_experience(text):
            start = cls._parse_date(job.start_date) if job.start_date else None
            end = cls._parse_date(job.end_date, end=True) if job.end_date else None
            if start and end and end >= start:
                spans.append((start, end))
        if not spans:
            return 0.0
        spans.sort()
        total_days, (cur_start, cur_end) = 0, spans[0]
        for start, end in spans[1:]:
            if start <= cur_end:
                cur_end = max(cur_end, end)
            else:
                total_days += (cur_end - cur_start).days
                cur_start, cur_end = start, end
        total_days += (cur_end - cur_start).days
        return round(total_days / 365.25, 1)

    @classmethod
    def parse_to_profile(cls, source_path_or_text: str, profile_id: str = "default_user") -> CandidateProfile:
        """Parses any PDF, DOCX, or text string into a structured CandidateProfile."""
        text = cls.extract_raw_text(source_path_or_text)
        contact = cls.extract_contact_info(text)
        all_skills, categorized_skills = cls.categorize_skills(text)
        education = cls.extract_education(text)
        experience, projects = cls.extract_projects_and_experience(text)
        estimated_yoe = cls.calculate_estimated_yoe(text, experience)

        # Certifications: only ones the resume says the person holds.
        certifications = []
        for line in cls._sections(text).get("other", []) + text.split("\n"):
            for m in re.finditer(r"\b(?:certified|certification:?)\s+([A-Z][\w &/+-]{3,60}?)(?=[.,;|\n]|$)", line):
                cert = m.group(0).strip(" .,;")
                if cert not in certifications:
                    certifications.append(cert)

        # Initial Recruiter Preferences
        prefs = RecruiterPreferences(
            years_of_experience=estimated_yoe,
            expected_ctc="15 LPA",
            current_ctc="0 LPA",
            notice_period_days=0,
            work_authorization="Citizen",
            remote_preference="Remote / Hybrid / On-site",
            why_looking_for_role=""  # the user's own words, asked for in setup
        )

        return CandidateProfile(
            id=profile_id,
            full_name=contact["full_name"],
            email=contact["email"],
            phone=contact["phone"],
            location=contact["location"],
            linkedin_url=contact["linkedin_url"],
            github_url=contact["github_url"],
            portfolio_url=contact["portfolio_url"],
            summary=cls.extract_summary(text),
            education=education,
            experience=experience,
            projects=projects,
            skills=all_skills,
            categorized_skills=categorized_skills,
            certifications=certifications,
            preferences=prefs,
            raw_resume_text=text
        )

    @classmethod
    async def parse_to_profile_async(
        cls,
        source_path_or_text: str,
        profile_id: str = "default_user",
        user_id: str = "default_user"
    ) -> CandidateProfile:
        """
        Asynchronously parses any PDF, DOCX, or text resume using LLM structured extraction,
        with seamless deterministic heuristic fallback to parse_to_profile().
        """
        text = await asyncio.to_thread(cls.extract_raw_text, source_path_or_text)
        fallback_profile = await asyncio.to_thread(cls.parse_to_profile, text, profile_id=profile_id)

        try:
            from app.core.llm_client import llm_client

            prompt = f"""
Extract structured candidate profile details from the following resume text:

--- RESUME TEXT ---
{text[:4000]}
--- END RESUME TEXT ---

Return a strictly valid JSON object with the following schema:
{{
    "full_name": "Candidate Full Name",
    "email": "candidate@example.com",
    "phone": "+1-000-000-0000",
    "location": "City, State / Country",
    "linkedin_url": "https://linkedin.com/in/... or null",
    "github_url": "https://github.com/... or null",
    "portfolio_url": "https://... or null",
    "summary": "Brief 2-3 sentence professional summary",
    "skills": ["Skill1", "Skill2"],
    "education": [
        {{"degree": "Degree name", "institution": "University/College", "graduation_year": "2024", "gpa": "3.8"}}
    ],
    "experience": [
        {{
            "company": "Company Name",
            "title": "Role Title",
            "start_date": "YYYY or Month YYYY",
            "end_date": "Present or Month YYYY",
            "location": "Remote / City",
            "highlights": ["Key achievement 1", "Key achievement 2"],
            "tech_stack": ["Tech1", "Tech2"]
        }}
    ],
    "projects": [
        {{
            "name": "Project Name",
            "description": "Project summary",
            "technologies": ["Tech1", "Tech2"],
            "metrics": "Impact metrics"
        }}
    ],
    "certifications": ["Cert 1", "Cert 2"],
    "years_of_experience": 3.5
}}
"""
            system_prompt = (
                "You are an expert ATS resume extraction engine. Extract high-fidelity structured profile details "
                "from resume text. Output strictly valid JSON."
            )

            res = await llm_client.chat_completion_json(
                prompt=prompt,
                system_prompt=system_prompt,
                fallback_fn=lambda: fallback_profile.dict(),
                user_id=user_id
            )

            if isinstance(res, dict) and (res.get("full_name") or res.get("email") or res.get("skills")):
                full_name = res.get("full_name") or fallback_profile.full_name
                email = res.get("email") or fallback_profile.email
                phone = res.get("phone") or fallback_profile.phone
                location = res.get("location") or fallback_profile.location
                linkedin = res.get("linkedin_url") or fallback_profile.linkedin_url
                github = res.get("github_url") or fallback_profile.github_url
                portfolio = res.get("portfolio_url") or fallback_profile.portfolio_url
                summary = res.get("summary") or fallback_profile.summary

                # Skills
                skills = res.get("skills") if isinstance(res.get("skills"), list) and res.get("skills") else fallback_profile.skills
                _, categorized_skills = cls.categorize_skills(" ".join(skills) + " " + text)

                # Education
                education_objs = []
                if isinstance(res.get("education"), list) and res.get("education"):
                    for ed in res["education"]:
                        if isinstance(ed, dict):
                            education_objs.append(Education(
                                degree=ed.get("degree", "Degree"),
                                institution=ed.get("institution", "University"),
                                graduation_year=str(ed.get("graduation_year", "2024")),
                                gpa=str(ed.get("gpa", "")) if ed.get("gpa") else None
                            ))
                if not education_objs:
                    education_objs = fallback_profile.education

                # Experience
                experience_objs = []
                if isinstance(res.get("experience"), list) and res.get("experience"):
                    for exp in res["experience"]:
                        if isinstance(exp, dict):
                            experience_objs.append(WorkExperience(
                                company=exp.get("company", "Technology Solutions"),
                                title=exp.get("title", "Software Engineer"),
                                start_date=str(exp.get("start_date", "2023")),
                                end_date=str(exp.get("end_date", "Present")),
                                location=exp.get("location", "Remote"),
                                highlights=exp.get("highlights", ["Engineered backend services."]),
                                tech_stack=exp.get("tech_stack", skills[:5])
                            ))
                if not experience_objs:
                    experience_objs = fallback_profile.experience

                # Projects
                project_objs = []
                if isinstance(res.get("projects"), list) and res.get("projects"):
                    for pr in res["projects"]:
                        if isinstance(pr, dict):
                            project_objs.append(Project(
                                name=pr.get("name", "Software Project"),
                                description=pr.get("description", "High-scale engineering project."),
                                technologies=pr.get("technologies", skills[:3]),
                                metrics=pr.get("metrics", "Sub-50ms latency")
                            ))
                if not project_objs:
                    project_objs = fallback_profile.projects

                certifications = res.get("certifications") if isinstance(res.get("certifications"), list) else fallback_profile.certifications
                try:
                    yoe = float(res.get("years_of_experience", fallback_profile.preferences.years_of_experience))
                except Exception:
                    yoe = fallback_profile.preferences.years_of_experience

                prefs = fallback_profile.preferences
                prefs.years_of_experience = yoe

                return CandidateProfile(
                    id=profile_id,
                    user_id=user_id,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    location=location,
                    linkedin_url=linkedin,
                    github_url=github,
                    portfolio_url=portfolio,
                    summary=summary,
                    education=education_objs,
                    experience=experience_objs,
                    projects=project_objs,
                    skills=skills,
                    categorized_skills=categorized_skills,
                    certifications=certifications,
                    preferences=prefs,
                    raw_resume_text=text
                )
        except Exception:
            logger.warning("resume_parser: structured parsing failed, falling back to basic profile", exc_info=True)
            pass

        return fallback_profile
