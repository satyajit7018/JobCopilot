"""
JobCopilot - Slot-Aware Semantic Vector & Lexical Hybrid Matcher
Maps arbitrary recruiter question strings to structured slot types using
dense embeddings and lexical token matching with Reciprocal Rank Fusion (RRF).
"""

import re
import math
from typing import List, Dict, Tuple, Optional
from collections import Counter
from app.core.models import SlotType


class SlotMatcher:
    """Hybrid semantic vector and lexical slot matcher with contextual disambiguation."""

    VOCABULARY = [
        "ctc", "salary", "compensation", "expected", "current", "notice", "period", "days",
        "immediate", "visa", "sponsorship", "citizen", "relocate", "relocation", "remote",
        "hybrid", "onsite", "experience", "years", "python", "javascript", "typescript", "react",
        "fastapi", "docker", "kubernetes", "aws", "gcp", "sql", "postgres", "redis", "pytorch",
        "machine", "learning", "ai", "vision", "why", "company", "team", "mission", "challenge",
        "project", "link", "portfolio", "github", "linkedin", "gender", "ethnicity", "race",
        "veteran", "disability", "eeo", "education", "degree", "university", "college", "gpa",
        "available", "availability", "start", "hire", "fit", "looking_change", "why_company"
    ]

    def tokenize(self, text: str) -> List[str]:
        return re.findall(r'\b[a-zA-Z0-9]+\b', text.lower())

    def get_embedding(self, text: str) -> List[float]:
        """Computes normalized dense subword vector representation with semantic synonym expansion."""
        tokens = self.tokenize(text)
        counts = Counter(tokens)
        text_lower = text.lower()
        
        vector = []
        for word in self.VOCABULARY:
            tf = float(counts.get(word, 0))

            # 1. Salary & Compensation
            if word == "salary" and any(k in counts for k in ["pay", "package", "lpa", "remuneration", "rate", "earnings", "ctc", "compensation"]):
                tf += 4.0

            # 2. Notice Period & Availability (Only if NOT a 'why' question)
            if "why" not in text_lower:
                if word == "notice" and any(k in counts for k in ["joining", "available", "availability", "start", "earliest", "soon", "period"]):
                    tf += 4.0
                if word == "days" and any(k in counts for k in ["notice", "joining", "start", "soon", "immediate"]):
                    tf += 3.0
                if word == "available" and any(k in counts for k in ["soon", "start", "join"]):
                    tf += 3.0

            # 3. Why Join Company vs Why Looking For Role vs Why Hire Me
            if "why" in text_lower:
                if word == "why":
                    tf += 3.0
                if word == "why_company" and any(k in counts for k in ["company", "team", "join", "work", "us", "firm", "interested", "excited"]):
                    tf += 6.0
                if word == "looking_change" and any(k in counts for k in ["looking", "leave", "leaving", "change", "new", "switch", "seeking"]):
                    tf += 6.0
                if word in ["hire", "fit"] and any(k in counts for k in ["hire", "candidate", "choose", "select"]):
                    tf += 6.0

            # 4. Technical Experience & YoE
            if word == "experience" and any(k in counts for k in ["yrs", "tenure", "duration", "years", "background", "proficiency"]):
                tf += 3.0
            if word == "relocate" and any(k in counts for k in ["move", "relocation", "onsite", "travel", "relocating"]):
                tf += 3.0
            if word == "sponsorship" and any(k in counts for k in ["visa", "authorization", "authorized", "citizen", "resident", "sponsor"]):
                tf += 4.0

            vector.append(tf)

        # L2 Normalize
        norm = math.sqrt(sum(x ** 2 for x in vector))
        if norm > 0:
            return [x / norm for x in vector]
        return [1.0 / len(self.VOCABULARY)] * len(self.VOCABULARY)

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

    def bm25_lexical_score(self, query: str, document: str) -> float:
        """Calculates lightweight BM25 lexical token match score."""
        q_tokens = set(self.tokenize(query))
        d_tokens = self.tokenize(document)
        if not q_tokens or not d_tokens:
            return 0.0
        d_counts = Counter(d_tokens)
        doc_len = len(d_tokens)
        avg_doc_len = 10.0
        k1 = 1.2
        b = 0.75

        score = 0.0
        for token in q_tokens:
            if token in d_counts:
                tf = d_counts[token]
                score += (tf * (k1 + 1)) / (tf + k1 * (1 - b + b * (doc_len / avg_doc_len)))
        return score

    def compute_hybrid_score(self, query: str, query_emb: List[float], doc_pattern: str, doc_emb: List[float]) -> float:
        """Combines dense cosine similarity with BM25 lexical score."""
        dense_score = self.cosine_similarity(query_emb, doc_emb)
        lexical_raw = self.bm25_lexical_score(query, doc_pattern)
        normalized_lexical = min(lexical_raw / 3.0, 1.0)
        return (0.65 * dense_score) + (0.35 * normalized_lexical)

    def detect_slot_type(self, question_text: str) -> Tuple[SlotType, str]:
        """Infers the high-confidence slot type and slot key from question text."""
        text = question_text.lower()

        # 1. Why Company / Why Hire Me / Why Looking (Parametric Essays)
        if "why" in text:
            if any(k in text for k in ["hire you", "hire me", "good fit", "right candidate", "choose you"]):
                return SlotType.PARAMETRIC_ESSAY, "why_hire_me"
            if any(k in text for k in ["looking for", "new role", "leaving", "switch"]):
                return SlotType.PARAMETRIC_ESSAY, "why_looking_for_role"
            if any(k in text for k in ["join", "work", "interested in", "company", "team", "us", "excited"]):
                return SlotType.PARAMETRIC_ESSAY, "why_join_company"

        # 2. Exact Recruiter Parameters
        if any(k in text for k in ["expected ctc", "expected salary", "desired compensation", "expected pay", "salary expectation", "compensation expectation"]):
            return SlotType.EXACT_PARAM, "expected_ctc"
        if any(k in text for k in ["current ctc", "current salary", "present compensation", "current pay"]):
            return SlotType.EXACT_PARAM, "current_ctc"
        if any(k in text for k in ["notice period", "how soon", "available to join", "earliest start date", "availability", "when can you start"]):
            return SlotType.EXACT_PARAM, "notice_period_days"
        if any(k in text for k in ["sponsorship", "visa required", "work authorization", "authorized to work", "legally authorized"]):
            return SlotType.EXACT_PARAM, "work_authorization"
        if any(k in text for k in ["relocate", "willingness to relocate", "relocation", "open to relocate"]):
            return SlotType.EXACT_PARAM, "willing_to_relocate"
        if any(k in text for k in ["remote", "hybrid", "on-site", "work from home", "work mode"]):
            return SlotType.EXACT_PARAM, "remote_preference"
        if any(k in text for k in ["total experience", "overall experience", "years of experience"]):
            return SlotType.EXACT_PARAM, "years_of_experience"

        # 3. Skill-Specific Experience Years
        tech_matches = ["python", "react", "fastapi", "docker", "aws", "gcp", "sql", "pytorch", "kubernetes", "typescript", "node"]
        for tech in tech_matches:
            if tech in text and any(k in text for k in ["experience", "years", "how long", "proficiency", "worked with"]):
                return SlotType.TECH_YEARS, f"TECH_YEARS:{tech.capitalize()}"

        # 4. Technical Achievements
        if any(k in text for k in ["describe a challenge", "project you built", "difficult bug", "proudest achievement", "technical achievement"]):
            return SlotType.PARAMETRIC_ESSAY, "technical_achievement"

        # 5. EEO & Demographics
        if any(k in text for k in ["gender", "race", "ethnicity", "veteran", "disability", "equal opportunity", "self-identify"]):
            return SlotType.SELECTION, "eeo_disclosure"

        return SlotType.FREEFORM, "general_question"
