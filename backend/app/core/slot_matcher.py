"""
JobCopilot - Slot-Aware Semantic Vector Matcher
Maps arbitrary recruiter question strings to structured slot types using dense embeddings.
"""

import re
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter
from app.core.models import SlotType


class SlotMatcher:
    def __init__(self):
        # Lexicon for dense subword/keyword vector representation
        self.vocabulary = [
            "ctc", "salary", "compensation", "expected", "current", "notice", "period", "days",
            "immediate", "visa", "sponsorship", "citizen", "relocate", "relocation", "remote",
            "hybrid", "onsite", "experience", "years", "python", "javascript", "react", "fastapi",
            "docker", "kubernetes", "aws", "gcp", "sql", "machine", "learning", "ai", "vision",
            "why", "join", "company", "mission", "challenge", "project", "link", "portfolio",
            "github", "linkedin", "gender", "ethnicity", "race", "veteran", "disability", "eeo"
        ]

    def tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b[a-zA-Z]+\b', text.lower())

    def get_embedding(self, text: str) -> List[float]:
        tokens = self.tokenize(text)
        counts = Counter(tokens)
        
        vector = []
        for word in self.vocabulary:
            tf = counts.get(word, 0)
            # Synonym expansion
            if word == "salary" and any(k in counts for k in ["pay", "package", "lpa", "remuneration", "rate"]):
                tf += 1.5
            if word == "notice" and any(k in counts for k in ["joining", "available", "start"]):
                tf += 1.5
            if word == "experience" and any(k in counts for k in ["yrs", "tenure", "duration"]):
                tf += 1.5
            vector.append(float(tf))

        # L2 Normalize
        norm = math.sqrt(sum(x ** 2 for x in vector))
        if norm > 0:
            return [x / norm for x in vector]
        return [1.0 / len(self.vocabulary)] * len(self.vocabulary)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0
        dot = sum(a * b for a, b in zip(vec_a, vec_b))
        norm_a = math.sqrt(sum(a ** 2 for a in vec_a))
        norm_b = math.sqrt(sum(b ** 2 for b in vec_b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def detect_slot_type(self, question_text: str) -> Tuple[SlotType, str]:
        text = question_text.lower()

        # 1. Exact Parameters
        if any(k in text for k in ["expected ctc", "expected salary", "desired compensation", "expected pay"]):
            return SlotType.EXACT_PARAM, "expected_ctc"
        if any(k in text for k in ["current ctc", "current salary", "present compensation"]):
            return SlotType.EXACT_PARAM, "current_ctc"
        if any(k in text for k in ["notice period", "how soon can you join", "earliest start date"]):
            return SlotType.EXACT_PARAM, "notice_period_days"
        if any(k in text for k in ["sponsorship", "visa required", "work authorization"]):
            return SlotType.EXACT_PARAM, "work_authorization"
        if any(k in text for k in ["relocate", "willingness to relocate", "relocation"]):
            return SlotType.EXACT_PARAM, "willing_to_relocate"
        if any(k in text for k in ["remote", "hybrid", "on-site", "work from home"]):
            return SlotType.EXACT_PARAM, "remote_preference"

        # 2. Skill Years Experience
        tech_matches = ["python", "react", "fastapi", "docker", "aws", "sql", "pytorch", "kubernetes"]
        for tech in tech_matches:
            if tech in text and any(k in text for k in ["experience", "years", "how long", "proficiency"]):
                return SlotType.TECH_YEARS, f"TECH_YEARS:{tech.capitalize()}"

        # 3. Parametric Essay
        if any(k in text for k in ["why do you want to join", "why this company", "why work with us"]):
            return SlotType.PARAMETRIC_ESSAY, "why_join_company"
        if any(k in text for k in ["describe a challenge", "project you built", "difficult bug", "proudest achievement"]):
            return SlotType.PARAMETRIC_ESSAY, "technical_achievement"

        # 4. EEO Selections
        if any(k in text for k in ["gender", "race", "ethnicity", "veteran", "disability"]):
            return SlotType.SELECTION, "eeo_disclosure"

        return SlotType.FREEFORM, "general_question"
