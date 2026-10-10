"""
JobCopilot - Multi-Factor Resume-to-Job Match Scorer
Computes multi-dimensional alignment: Technical Skills (40%), Title Relevance (30%),
Experience Years (15%), and Location/Remote Compatibility (15%).
"""

import re
from typing import List, Optional, Tuple

from app.core.models import CandidateProfile


class MatchScorer:
    """Multi-factor candidate-to-job matching engine."""

    SENIORITY_YOE_MAP = {
        "intern": (0.0, 1.0),
        "junior": (0.0, 2.0),
        "entry": (0.0, 2.0),
        "mid": (2.0, 5.0),
        "senior": (4.0, 9.0),
        "lead": (5.0, 12.0),
        "staff": (7.0, 15.0),
        "principal": (10.0, 20.0),
        "director": (10.0, 25.0)
    }

    @classmethod
    def extract_job_required_skills(cls, job_text: str) -> List[str]:
        """Extracts technical skills required from job description."""
        from app.core.resume_parser import ResumeParser
        all_skills, _ = ResumeParser.categorize_skills(job_text)
        return all_skills

    @classmethod
    def infer_job_seniority(cls, title: str, description: str) -> str:
        """Infers job seniority level from title and description text using word boundaries."""
        t_clean = (title or "").lower()
        # Title takes strict priority
        if re.search(r'\b(intern|internship)\b', t_clean):
            return "Intern"
        if re.search(r'\bstaff\b', t_clean):
            return "Staff"
        if re.search(r'\bprincipal\b', t_clean):
            return "Principal"
        if re.search(r'\blead\b', t_clean):
            return "Lead"
        if re.search(r'\b(senior|sr\.)\b', t_clean):
            return "Senior"
        if re.search(r'\b(junior|jr\.|entry|graduate)\b', t_clean):
            return "Junior"

        # Check description intro (first 300 chars) with word boundaries if title had no seniority token
        desc_intro = (description or "")[:300].lower()
        if re.search(r'\b(intern|internship)\b', desc_intro):
            return "Intern"
        if re.search(r'\bstaff\b', desc_intro):
            return "Staff"
        if re.search(r'\bprincipal\b', desc_intro):
            return "Principal"
        if re.search(r'\blead\b', desc_intro):
            return "Lead"
        if re.search(r'\b(senior|sr\.)\b', desc_intro):
            return "Senior"
        if re.search(r'\b(junior|jr\.|entry|graduate)\b', desc_intro):
            return "Junior"

        return "Mid-Level"

    # Spelling variants of the same skill count once.
    SKILL_ALIASES = {
        "golang": "go",
        "postgres": "postgresql",
        "react.js": "react",
        "vue.js": "vue",
        "amazon web services": "aws",
        "google cloud": "gcp",
        "apache kafka": "kafka",
    }
    # Mentioned in nearly every posting (or a company name), so they say nothing about fit.
    LOW_SIGNAL_SKILLS = {"git", "github", "jira", "postman"}
    # Short names that are also ordinary words; only trust a case-sensitive mention.
    AMBIGUOUS_SKILLS = {
        "go": re.compile(r"(?<![\w-])(?:Go(?![\w-])(?!\s+(?:to|above|beyond|live)\b)|Golang)"),
        "r": re.compile(r"(?<![\w&/.-])R(?![\w&/+-])(?!\s*&)"),
    }

    NON_TECH_TITLE = re.compile(
        r"\b(sales|account (?:executive|manager)|marketing|recruit\w*|talent|designer|design|"
        r"legal|counsel|finance|accountant|payroll|support|customer|success|operations|"
        r"partnerships?|communications|writer|content|trainer|training|translator|"
        r"specialist|coordinator|assistant|analyst|business development|hr|people)\b"
    )
    TECH_TITLE = re.compile(
        r"\b(engineer\w*|developer|programmer|sre|devops|architect|scientist|researcher|swe|sde|mts|technical staff)\b"
    )
    # "Engineer" titles that are really support, IT, sales or advocacy work.
    ADJACENT_TITLE = re.compile(
        r"\b(support|it|helpdesk|solutions?|sales|pre-?sales|customer|field|implementation|"
        r"developer relations|devrel|advocate|forward deployed|deployment strategist)\b"
    )
    MANAGER_TITLE = re.compile(r"\b(manager|director|head|vp|vice president|chief|cto)\b")

    # Job-title specialties and the skills that signal them.
    SPECIALTIES = {
        "backend": (re.compile(r"\b(back[- ]?end|api|server|platform|distributed systems?|payments?)\b"),
                    {"python", "go", "java", "kotlin", "scala", "rust", "c#", "ruby", "php", "node.js", "fastapi",
                     "django", "flask", "spring boot", "express.js", "postgresql", "mysql", "redis", "kafka",
                     "mongodb", "rabbitmq", "celery", "graphql", "cassandra", "dynamodb"}),
        "frontend": (re.compile(r"\b(front[- ]?end|ui|web)\b"),
                     {"javascript", "typescript", "react", "vue", "angular", "next.js", "html", "css",
                      "tailwindcss", "redux"}),
        "fullstack": (re.compile(r"\bfull[- ]?stack\b"),
                      {"javascript", "typescript", "react", "next.js", "node.js", "python", "django", "fastapi",
                       "postgresql", "mongodb", "express.js"}),
        "ml": (re.compile(r"\b(ai|ml|machine learning|data scien\w*|nlp|computer vision|llms?|research scientist|"
                          r"applied scientist|deep learning)\b"),
               {"pytorch", "tensorflow", "keras", "scikit-learn", "pandas", "numpy", "langchain", "llamaindex",
                "opencv"}),
        "data": (re.compile(r"\b(data (?:engineer\w*|platform|infrastructure)|etl|analytics engineer\w*)\b"),
                 {"sql", "python", "kafka", "snowflake", "bigquery", "pandas", "scala", "postgresql"}),
        "devops": (re.compile(r"\b(devops|sre|site reliability|infrastructure|cloud|reliability)\b"),
                   {"docker", "kubernetes", "terraform", "aws", "gcp", "azure", "helm", "ansible", "linux",
                    "ci/cd", "github actions", "nginx"}),
        "mobile": (re.compile(r"\b(ios|android|mobile)\b"),
                   {"swift", "kotlin", "react native", "flutter"}),
    }

    @classmethod
    def _canonical_skill(cls, skill: str) -> str:
        key = skill.lower().strip()
        return cls.SKILL_ALIASES.get(key, key)

    @classmethod
    def _job_skills(cls, job_title: str, job_description: str) -> List[str]:
        """Skills a posting asks for: aliases merged, noise dropped, ambiguous names verified."""
        raw_text = f"{job_title}\n{job_description}"
        out: List[str] = []
        seen = set()
        for skill in cls.extract_job_required_skills(raw_text):
            key = cls._canonical_skill(skill)
            if key in cls.LOW_SIGNAL_SKILLS or key in seen:
                continue
            check = cls.AMBIGUOUS_SKILLS.get(key)
            if check is not None and not check.search(raw_text):
                continue
            seen.add(key)
            out.append(skill)
        return out

    @classmethod
    def _candidate_is_manager(cls, profile: CandidateProfile) -> bool:
        titles = " ".join((exp.title or "") for exp in (profile.experience or [])).lower()
        return bool(cls.MANAGER_TITLE.search(titles))

    REGIONS = {
        "india": re.compile(r"\b(india|bangalore|bengaluru|hyderabad|pune|delhi|ncr|gurgaon|gurugram|noida|mumbai|"
                            r"chennai|kolkata|ahmedabad|jaipur|kochi|karnataka|maharashtra|telangana|tamil nadu)\b"),
        "usa": re.compile(r"\b(usa|u\.s\.a?\.?|united states|us|amer|north america|new york|nyc|san francisco|sf|"
                          r"seattle|austin|boston|chicago|los angeles|denver|california|washington|texas)\b"),
        "europe": re.compile(r"\b(uk|united kingdom|london|europe|emea|eu|germany|berlin|munich|amsterdam|"
                             r"netherlands|paris|france|dublin|ireland|spain|madrid|lisbon|portugal|poland|"
                             r"warsaw|stockholm|sweden|zurich|switzerland)\b"),
        "canada": re.compile(r"\b(canada|toronto|vancouver|montreal)\b"),
    }

    @classmethod
    def _regions(cls, text: str) -> set:
        """Broad regions a location string mentions (word matches, so 'us' never hits 'Australia')."""
        if not text:
            return set()
        text = text.lower()
        return {name for name, pattern in cls.REGIONS.items() if pattern.search(text)}

    @classmethod
    def _onsite_abroad(cls, profile: CandidateProfile, job_location: str) -> bool:
        """An office-based job in a different country from the candidate's."""
        loc = (job_location or "").lower()
        if re.search(r"\bremote\b", loc):
            return False
        job_regions, cand_regions = cls._regions(loc), cls._regions(profile.location or "")
        return bool(job_regions and cand_regions and not (job_regions & cand_regions))

    @classmethod
    def _location_fit(cls, profile: CandidateProfile, job_location: str) -> Tuple[float, Optional[str]]:
        """0-1 fit between the job's location and where the candidate is / wants to work."""
        loc = (job_location or "").lower()
        prefs = profile.preferences
        pref = (prefs.remote_preference if prefs else "").lower()
        wants_remote = "remote" in pref
        remote_only = wants_remote and not any(w in pref for w in ("hybrid", "on-site", "onsite", "office"))
        willing = prefs.willing_to_relocate if prefs else False
        cand = (profile.location or "").lower()

        job_regions = cls._regions(loc)
        cand_regions = cls._regions(cand)
        same_region = bool(job_regions & cand_regions)
        # City-level words from the candidate's location ("Pune, India" -> "pune").
        not_cities = {"india", "usa", "us", "united states", "uk", "remote", "karnataka", "maharashtra",
                      "telangana", "tamil nadu", "california", "washington", "texas", "new york state"}
        city_tokens = [t.strip() for t in re.split(r"[,/|()•-]", cand) if len(t.strip()) > 2 and t.strip() not in not_cities]
        same_city = any(re.search(r"\b" + re.escape(t) + r"\b", loc) for t in city_tokens)

        if re.search(r"\bremote\b", loc):
            # "Remote (India)" style postings are limited to that region.
            if job_regions and not same_region:
                return 0.3, None
            return (1.0 if wants_remote else 0.8), "Remote role, matching your work preference." if wants_remote else None
        if same_city:
            return 1.0, "In or near your city."
        if remote_only:
            return 0.15, None
        if same_region:
            return (0.8 if willing else 0.5), "In your country."
        return (0.35 if willing else 0.1), None

    @classmethod
    def compute_match_score(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str,
        job_location: str = "Remote"
    ) -> Tuple[float, List[str], List[str]]:
        """
        Weighted match score (0.05-0.99) with reasons and missing skills:
        skills 45%, role fit 25%, experience 15%, location 15%.

        A posting only scores high when several of its skills match, the role is
        one the candidate does, the level fits and the location works. A single
        shared skill, a non-engineering role or a far-away office keeps it low.
        """
        candidate_skills = profile.skills or []
        candidate_keys = {cls._canonical_skill(s): s for s in candidate_skills}

        match_reasons: List[str] = []
        missing_skills: List[str] = []

        has_resume_data = bool(
            (getattr(profile, "raw_resume_text", None) and profile.raw_resume_text.strip()) or
            (profile.skills and len(profile.skills) > 0) or
            (profile.experience and len(profile.experience) > 0) or
            (profile.summary and profile.summary.strip())
        )

        title_clean = (job_title or "").lower()
        is_tech = bool(cls.TECH_TITLE.search(title_clean))
        is_non_tech = not is_tech and bool(cls.NON_TECH_TITLE.search(title_clean))
        is_manager_role = bool(cls.MANAGER_TITLE.search(title_clean))

        # 1. Skills (45%): share of the posting's skills you have, scaled by how many
        # match, so one overlapping keyword can't carry the score.
        job_skills = cls._job_skills(job_title, job_description)
        matched_skills: List[str] = []
        for js in job_skills:
            key = cls._canonical_skill(js)
            if key in candidate_keys:
                matched_skills.append(candidate_keys[key])
            else:
                missing_skills.append(js)

        avg_multiplier = 1.0
        try:
            from app.analytics.feedback_loop import ConversionFeedbackLoop
            user_id = getattr(profile, "user_id", "default") or "default"
            if matched_skills:
                m_sum = sum(ConversionFeedbackLoop.get_feature_multiplier(user_id, "skill", ms) for ms in matched_skills)
                avg_multiplier = m_sum / len(matched_skills)
        except Exception:
            avg_multiplier = 1.0

        skill_score = 0.0
        if job_skills and matched_skills:
            coverage = min(len(matched_skills) / len(job_skills) * avg_multiplier, 1.0)
            depth = min(len(matched_skills) / 4.0, 1.0)
            skill_score = 0.45 * (0.55 * coverage + 0.45 * depth)
            reasons_text = f"Matches {len(matched_skills)} of {len(job_skills)} skills it asks for: {', '.join(matched_skills[:4])}"
            if avg_multiplier > 1.05:
                reasons_text += f" (+{int((avg_multiplier - 1.0) * 100)}% empirical callback lift)"
            match_reasons.append(reasons_text)

        # 2. Role fit (25%)
        role_score = 0.0
        if is_tech:
            if is_manager_role and not cls._candidate_is_manager(profile):
                role_score = 0.03
            elif cls.ADJACENT_TITLE.search(title_clean):
                role_score = 0.05
            else:
                specialties = [(name, skills) for name, (pattern, skills) in cls.SPECIALTIES.items() if pattern.search(title_clean)]
                if not specialties:
                    role_score = 0.18  # generic "Software Engineer"
                else:
                    best_name, best_hits = None, 0
                    for name, skills in specialties:
                        hits = len(skills & set(candidate_keys))
                        if hits > best_hits:
                            best_name, best_hits = name, hits
                    role_score = 0.25 if best_hits >= 3 else 0.17 if best_hits == 2 else 0.08 if best_hits == 1 else 0.02
                    if best_hits >= 3:
                        label = {"ml": "AI / ML", "devops": "DevOps / infrastructure", "fullstack": "full-stack"}.get(best_name, best_name)
                        match_reasons.append(f"Role fits your {label} background.")

        # 3. Experience level (15%)
        seniority = cls.infer_job_seniority(job_title, job_description)
        yoe = profile.preferences.years_of_experience if profile.preferences else 0.0
        min_yoe, max_yoe = cls.SENIORITY_YOE_MAP.get(seniority.lower(), (1.0, 6.0))
        exp_score = 0.0
        if is_tech:
            if not has_resume_data or (not profile.skills and yoe <= 0.0):
                exp_score = 0.05
                match_reasons.append("Rough score for now. Add your resume in Profile for an accurate one.")
            elif min_yoe <= yoe <= max_yoe + 1.0:
                exp_score = 0.15
                years = f"{yoe:g} year{'' if yoe == 1 else 's'}"
                role = "an internship" if seniority == "Intern" else f"a {seniority.lower()} role"
                match_reasons.append(f"Your {years} of experience fits {role}.")
            elif yoe < min_yoe:
                exp_score = max(0.0, 0.15 - (min_yoe - yoe) * 0.05)
            else:
                exp_score = 0.08

        # 4. Location (15%)
        loc_fit, loc_reason = cls._location_fit(profile, job_location)
        loc_score = 0.15 * loc_fit if is_tech else 0.0
        if is_tech and loc_reason:
            match_reasons.append(loc_reason)

        total_score = skill_score + role_score + exp_score + loc_score
        # Level and location alone can't make a strong match: it needs shared skills.
        if len(matched_skills) <= 1:
            total_score = min(total_score, 0.55)
        elif len(matched_skills) == 2:
            total_score = min(total_score, 0.75)
        if is_non_tech:
            total_score = min(total_score, 0.20)
        if is_tech and cls._onsite_abroad(profile, job_location):
            # Visas and relocation make these long shots, however good the fit.
            total_score = min(total_score, 0.70)
        if not has_resume_data or not profile.skills:
            # Cap provisional uncalibrated profiles so they do not claim false high confidence
            total_score = min(total_score, 0.35)
        final_clamped = min(max(round(total_score, 2), 0.05), 0.99)

        return final_clamped, match_reasons, missing_skills[:6]

    @classmethod
    def compute_match_score_semantic(
        cls,
        profile: CandidateProfile,
        job_title: str,
        job_description: str,
        job_location: str = "Remote"
    ) -> Tuple[float, List[str], List[str]]:
        """
        Computes multi-factor match score enhanced with dense semantic vector similarity:
        - 40% Semantic Vector Alignment (deep conceptual match between profile narrative and job requirements)
        - 60% Rule-Based Multidimensional Factors (skills, title, experience, location)
        """
        from app.core.llm_client import llm_client

        base_score, match_reasons, missing_skills = cls.compute_match_score(
            profile, job_title, job_description, job_location
        )

        has_resume_data = bool(
            (getattr(profile, "raw_resume_text", None) and profile.raw_resume_text.strip()) or
            (profile.skills and len(profile.skills) > 0) or
            (profile.experience and len(profile.experience) > 0) or
            (profile.summary and profile.summary.strip())
        )

        if not has_resume_data or not profile.skills:
            return base_score, match_reasons, missing_skills

        profile_text = (
            f"{profile.summary} "
            f"Skills: {', '.join(profile.skills[:15])}. "
            f"Experience: {' '.join(h for exp in profile.experience for h in exp.highlights[:2])}"
        ).strip()
        job_text = f"{job_title}. Description: {job_description[:2000]}".strip()

        try:
            p_vec = llm_client.embed_text_sync(profile_text)
            j_vec = llm_client.embed_text_sync(job_text)
            semantic_sim = llm_client.cosine_similarity(p_vec, j_vec)
            normalized_sim = max(0.0, min(1.0, (semantic_sim + 1.0) / 2.0 if semantic_sim < 0 else semantic_sim))
        except Exception:
            normalized_sim = base_score

        blended_score = (normalized_sim * 0.40) + (base_score * 0.60)
        final_score = min(max(round(blended_score, 2), 0.05), 0.99)

        if normalized_sim >= 0.65:
            match_reasons.insert(0, f"High semantic vector alignment ({int(normalized_sim * 100)}% conceptual fit)")

        return final_score, match_reasons, missing_skills
