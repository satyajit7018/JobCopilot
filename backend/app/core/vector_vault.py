"""
JobCopilot - Self-Learning Hybrid Knowledge Vault
Indexes Q&A pairs with semantic embeddings, lexical token matching,
and deterministic slot key resolution for zero-repeat autonomous form filling.
"""

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.core.database import db
from app.core.models import CandidateProfile, SlotType, VaultEntry
from app.core.slot_matcher import SlotMatcher

# Questions answered straight from the profile (fields the user has saved). The profile is the
# one place these facts live, so a stored copy of them is never used in their place.
PROFILE_SLOTS = {
    "expected_ctc": "{expected_ctc}",
    "current_ctc": "{current_ctc}",
    "notice_period_days": "{notice_period}",
    "work_authorization": "{work_authorization}",
    "requires_sponsorship": "{sponsorship_answer}",
    "willing_to_relocate": "{relocation_answer}",
    "remote_preference": "{remote_preference}",
    "years_of_experience": "{years_of_experience} years",
}

# Answers about one company ("Why do you want to work here?") are saved for that job only.
COMPANY_SPECIFIC_KEYS = {"why_join_company"}

# Personal questions: always optional, "Prefer not to say" unless the user chose an answer.
PERSONAL_KEYS = {"gender", "race_ethnicity", "veteran_status", "disability_status", "sexual_orientation", "eeo_disclosure"}
PREFER_NOT_TO_SAY = "Prefer not to say"

# Topics with one answer each, reused whatever the wording ("notice period", "years with Python").
# Written answers (essays) are reused only for the same wording or one the user confirmed.
ONE_ANSWER_TYPES = {SlotType.EXACT_PARAM, SlotType.TECH_YEARS, SlotType.SELECTION}

SEEDED_REASON_QUESTION = "Why are you looking for a new role?"

# Older versions copied profile defaults into every user's saved answers, and gave total years
# of experience as the years with each skill. Those copies are ignored, never trusted.
LEGACY_SEEDED_QUESTIONS = {
    "what is your expected ctc / compensation?",
    "what is your current ctc / salary?",
    "what is your notice period / earliest start date?",
    "are you open to relocation?",
    "do you require visa sponsorship?",
}
LEGACY_SKILL_YEARS = re.compile(r"^how many years of experience do you have with .+\?$")
LEGACY_SKILL_YEARS_ANSWER = re.compile(r"^(\d+\.\d years|1 year)$")

PLACEHOLDER = re.compile(r"\{[a-z_]+\}")


def normalize_question(text: str) -> str:
    """Wording compared for "the same question": case, punctuation, "*" and "(required)" ignored."""
    t = re.sub(r"\((required|optional)\)", " ", (text or "").lower())
    t = re.sub(r"[^a-z0-9+#]+", " ", t)
    return " ".join(t.split())


@dataclass
class AnswerMatch:
    """What we know for one form question.

    `answer` is safe to put on the form: from the profile, the user's saved answer to the same
    (or a confirmed) wording, or "Prefer not to say" for a personal question. `suggestion` is
    the user's answer to a similar question: shown marked "check this", never sent unconfirmed.
    """
    answer: Optional[str] = None
    source: str = "none"  # profile | saved | default | none
    entry: Optional[VaultEntry] = None
    suggestion: Optional[str] = None
    suggestion_entry: Optional[VaultEntry] = None
    score: float = 0.0
    slot_key: str = "general_question"
    optional: bool = False


class KnowledgeVault:
    """Self-learning Knowledge Vault storing and resolving recruiter Q&As with in-memory caching."""

    def __init__(self):
        self.matcher = SlotMatcher()
        self._cached_entries: Optional[List[VaultEntry]] = None

    def _get_entries(self, user_id: str) -> List[VaultEntry]:
        """Retrieves cached vault entries or reads from database for user."""
        return db.get_vault_entries(user_id=user_id)

    def seed_from_profile(self, profile: CandidateProfile):
        """Keeps the user's own "why I'm looking" words as a reusable answer.

        Salary, notice period and the other profile facts are read from the profile when a form
        asks (see PROFILE_SLOTS), so they are not copied here, where they would go stale.
        """
        reason = (profile.preferences.why_looking_for_role or "").strip()
        if reason:
            self.learn_answer(
                SEEDED_REASON_QUESTION,
                reason,
                slot_type=SlotType.PARAMETRIC_ESSAY,
                slot_key="why_looking_for_role",
                user_id=profile.user_id or "default",
                confirmed=False,
            )

    def learn_answer(
        self,
        question: str,
        answer_template: str,
        slot_type: Optional[SlotType] = None,
        slot_key: Optional[str] = None,
        user_id: str = "default",
        job_id: Optional[str] = None,
        confirmed: bool = True,
    ) -> VaultEntry:
        """Saves the user's answer to a question, replacing their earlier answer to the same question.

        Company-specific answers are kept for that one job. `confirmed` marks an answer the user
        gave or checked themselves (always, except answers copied from the profile).
        """
        if not slot_type or not slot_key:
            slot_type, slot_key = self.matcher.detect_slot_type(question)
        slot_type = SlotType(slot_type)
        scope = "job" if slot_key in COMPANY_SPECIFIC_KEYS else "any"
        job_id = job_id if scope == "job" else None
        now = datetime.now().isoformat()
        embedding = self.matcher.get_embedding(question)
        wording = normalize_question(question)

        def same_question(e: VaultEntry) -> bool:
            if e.scope != scope or (scope == "job" and e.job_id != job_id):
                return False
            if wording and (normalize_question(e.question_pattern) == wording or wording in {normalize_question(a) for a in e.aliases}):
                return True
            return slot_type in ONE_ANSWER_TYPES and e.slot_key == slot_key and e.slot_type == slot_type

        for e in self._get_entries(user_id=user_id):
            if same_question(e):
                e.slot_key = slot_key
                e.slot_type = slot_type
                e.answer_template = answer_template
                if normalize_question(e.question_pattern) != wording:
                    e.aliases = [a for a in e.aliases if normalize_question(a) != wording]
                    e.question_pattern = question
                    e.embedding = embedding
                e.last_used_at = now
                if confirmed:
                    e.confirmed_at = now
                db.save_vault_entry(e, user_id=user_id)
                return e

        entry = VaultEntry(
            qa_id=f"qa_{uuid.uuid4().hex[:8]}",
            user_id=user_id,
            slot_type=slot_type,
            slot_key=slot_key,
            question_pattern=question,
            embedding=embedding,
            answer_template=answer_template,
            dynamic_variables=["company", "role", "domain", "expected_ctc", "github_url", "linkedin_url"],
            usage_count=1,
            last_used_at=now,
            scope=scope,
            job_id=job_id,
            confirmed_at=now if confirmed else None,
        )
        db.save_vault_entry(entry, user_id=user_id)
        return entry

    def _find_own(self, user_id: str, qa_id: str) -> Optional[VaultEntry]:
        return next((e for e in self._get_entries(user_id=user_id) if e.qa_id == qa_id), None) if user_id else None

    def update_answer(self, user_id: str, qa_id: str, answer: str) -> Optional[VaultEntry]:
        """The user edits one of their saved answers."""
        entry = self._find_own(user_id, qa_id)
        if not entry:
            return None
        entry.answer_template = answer
        entry.confirmed_at = datetime.now().isoformat()
        db.save_vault_entry(entry, user_id=user_id)
        return entry

    def add_wording(self, user_id: str, qa_id: str, question: str) -> Optional[VaultEntry]:
        """The user confirms another wording means the same question; it then fills automatically."""
        entry = self._find_own(user_id, qa_id)
        if not entry:
            return None
        wording = normalize_question(question)
        known = {normalize_question(entry.question_pattern), *(normalize_question(a) for a in entry.aliases)}
        if wording and wording not in known:
            entry.aliases = [*entry.aliases, question.strip()]
        entry.confirmed_at = datetime.now().isoformat()
        db.save_vault_entry(entry, user_id=user_id)
        return entry

    def delete_answer(self, user_id: str, qa_id: str) -> bool:
        return bool(user_id) and db.delete_vault_entry(qa_id, user_id=user_id)

    @staticmethod
    def _profile_values(profile: CandidateProfile) -> Dict[str, str]:
        """What the profile can say for real. Preference fields count only once the user has saved them."""
        prefs = profile.preferences
        confirmed = set(getattr(prefs, "confirmed", None) or [])

        def text(value: Any) -> str:
            return str(value or "").strip()

        values: Dict[str, str] = {}
        if "expected_ctc" in confirmed:
            values["expected_ctc"] = text(prefs.expected_ctc)
        if "current_ctc" in confirmed and text(prefs.current_ctc).upper() != "0 LPA":
            values["current_ctc"] = text(prefs.current_ctc)
        if "notice_period_days" in confirmed:
            days = int(prefs.notice_period_days or 0)
            values["notice_period"] = "Immediately" if days == 0 else f"{days} days"
        if "work_authorization" in confirmed:
            values["work_authorization"] = text(prefs.work_authorization)
        if "requires_sponsorship" in confirmed:
            values["sponsorship_answer"] = "Yes" if prefs.requires_sponsorship else "No"
        if "willing_to_relocate" in confirmed:
            values["relocation_answer"] = "Yes" if prefs.willing_to_relocate else "No"
        if "remote_preference" in confirmed:
            values["remote_preference"] = text(prefs.remote_preference)
        if "years_of_experience" in confirmed and prefs.years_of_experience is not None:
            values["years_of_experience"] = f"{float(prefs.years_of_experience):g}"
        skills = [text(s) for s in (profile.skills or []) if text(s)]
        if skills:
            values["top_skills"] = ", ".join(skills[:5])
        for field in ("full_name", "email", "phone", "location", "github_url", "linkedin_url", "portfolio_url"):
            if text(getattr(profile, field, "")):
                values[field] = text(getattr(profile, field))
        return values

    def _resolve_template(
        self,
        template: str,
        profile: Optional[CandidateProfile],
        company: str,
        role: str,
        domain: str
    ) -> Optional[str]:
        """Fills {placeholders} with real values. None if any of them isn't known.

        An application never gets a default, a guess or a leftover {placeholder}: if the
        answer can't be completed from what the user told us, it is left for the user.
        """
        values: Dict[str, str] = {}
        if (company or "").strip() and company.strip().lower() not in ("company", "the company"):
            values["company"] = company.strip()
        if (role or "").strip():
            values["role"] = role.strip()
        if (domain or "").strip():
            values["domain"] = domain.strip()
        if profile:
            values.update(self._profile_values(profile))

        resolved = PLACEHOLDER.sub(lambda m: values.get(m.group(0)[1:-1]) or m.group(0), template or "")
        if not resolved.strip() or PLACEHOLDER.search(resolved):
            return None
        return resolved

    @staticmethod
    def _is_legacy_copy(entry: VaultEntry) -> bool:
        question = (entry.question_pattern or "").strip().lower()
        if question in LEGACY_SEEDED_QUESTIONS:
            return True
        return bool(LEGACY_SKILL_YEARS.match(question) and LEGACY_SKILL_YEARS_ANSWER.match((entry.answer_template or "").strip()))

    def _own_entries(self, user_id: str) -> List[VaultEntry]:
        """The user's own saved answers. Old shared defaults ("system_baseline") and stale copies are left out."""
        if not user_id or user_id == "system_baseline":
            return []
        return [e for e in self._get_entries(user_id=user_id) if not self._is_legacy_copy(e)]

    def find_answer(
        self,
        question: str,
        profile: Optional[CandidateProfile] = None,
        user_id: str = "",
        job_id: Optional[str] = None,
        company: str = "",
        role: str = "",
        domain: str = "",
        similarity_threshold: float = 0.55,
    ) -> AnswerMatch:
        """The user's answer to an application question, or a suggestion for them to check.

        Answers come only from the user: profile fields they have saved, or answers they gave
        before to the same question. A similar-looking question only ever gets a suggestion.
        """
        target_user = user_id or (profile.user_id if profile else "")
        usable = [
            e for e in self._own_entries(target_user)
            if e.scope != "job" or (job_id and e.job_id == job_id)
        ]
        detected_type, detected_key = self.matcher.detect_slot_type(question)
        empty = AnswerMatch(slot_key=detected_key, optional=detected_key in PERSONAL_KEYS)

        def filled(template: str, source: str, entry: Optional[VaultEntry] = None) -> Optional[AnswerMatch]:
            resolved = self._resolve_template(template, profile, company, role, domain)
            if not resolved:
                return None
            if entry:
                db.increment_vault_usage(entry.qa_id)
            return AnswerMatch(answer=resolved, source=source, entry=entry, score=1.0,
                               slot_key=detected_key, optional=empty.optional)

        # 1. The same wording, or one the user confirmed means the same.
        wording = normalize_question(question)
        for entry in usable:
            if wording and (normalize_question(entry.question_pattern) == wording
                            or wording in {normalize_question(a) for a in entry.aliases}):
                match = filled(entry.answer_template, "saved", entry)
                if match:
                    return match

        # 2. A topic with one answer: the profile first, then the user's saved answer.
        if detected_key in COMPANY_SPECIFIC_KEYS:
            return empty
        if detected_key in PROFILE_SLOTS and profile is not None:
            match = filled(PROFILE_SLOTS[detected_key], "profile")
            if match:
                return match
        if detected_type in ONE_ANSWER_TYPES and detected_key != "general_question":
            for entry in usable:
                if entry.slot_key == detected_key and entry.slot_type == detected_type:
                    match = filled(entry.answer_template, "saved", entry)
                    if match:
                        return match
            if detected_key in PERSONAL_KEYS:
                return AnswerMatch(answer=PREFER_NOT_TO_SAY, source="default", score=1.0, slot_key=detected_key, optional=True)
            # Salary, notice period, years with a skill: never taken from a lookalike question.
            return empty

        # 3. Anything else: the user's answer to a similar question, as a suggestion only.
        reusable = [
            e for e in usable
            if e.scope == "any" and e.slot_key not in COMPANY_SPECIFIC_KEYS and e.slot_key not in PERSONAL_KEYS
        ]
        best_entry, best_score = None, 0.0
        if detected_key != "general_question":
            # A written answer on the same topic ("Why should we hire you?") is the closest match.
            best_entry = next((e for e in reusable if e.slot_key == detected_key), None)
            best_score = 1.0 if best_entry else 0.0
        if not best_entry:
            query_embedding = self.matcher.get_embedding(question)
            for entry in reusable:
                doc_emb = entry.embedding
                if len(doc_emb) != len(query_embedding):
                    doc_emb = self.matcher.get_embedding(entry.question_pattern)
                score = self.matcher.compute_hybrid_score(question, query_embedding, entry.question_pattern, doc_emb)
                if score > best_score:
                    best_entry, best_score = entry, score
        if not best_entry or best_score < similarity_threshold:
            for sem_entry, sem_score in self.search_semantic(question, user_id=target_user, top_k=1):
                if sem_score >= similarity_threshold and sem_entry in reusable:
                    best_entry, best_score = sem_entry, sem_score
        if best_entry and best_score >= similarity_threshold:
            suggestion = self._resolve_template(best_entry.answer_template, profile, company, role, domain)
            if suggestion:
                return AnswerMatch(suggestion=suggestion, suggestion_entry=best_entry, score=best_score,
                                   slot_key=detected_key, optional=empty.optional)
        return AnswerMatch(score=best_score, slot_key=detected_key, optional=empty.optional)

    def query_answer(
        self,
        question: str,
        profile: Optional[CandidateProfile] = None,
        company: str = "",
        role: str = "",
        domain: str = "",
        similarity_threshold: float = 0.55,
        user_id: str = "",
        job_id: Optional[str] = None,
    ) -> Tuple[Optional[str], float, Optional[VaultEntry]]:
        """(answer, score, entry) for an answer that may go on the form; (None, score, None) otherwise."""
        match = self.find_answer(question, profile=profile, user_id=user_id, job_id=job_id, company=company,
                                 role=role, domain=domain, similarity_threshold=similarity_threshold)
        if match.answer and match.source in ("profile", "saved"):
            return match.answer, match.score, match.entry
        return None, match.score, None

    def search_semantic(
        self,
        query: str,
        user_id: str = "default",
        top_k: int = 5
    ) -> List[Tuple[VaultEntry, float]]:
        """
        Ranks knowledge vault entries strictly by dense semantic vector similarity.
        Returns top_k (VaultEntry, similarity_score) pairs.
        """
        from app.core.llm_client import llm_client

        entries = self._own_entries(user_id)
        if not entries:
            return []

        query_vec = llm_client.embed_text_sync(query)
        scored = []
        for entry in entries:
            doc_vec = entry.embedding
            if not doc_vec or len(doc_vec) != len(query_vec):
                doc_vec = llm_client.embed_text_sync(entry.question_pattern)
            sim = llm_client.cosine_similarity(query_vec, doc_vec)
            scored.append((entry, sim))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[:top_k]

    def get_answer_for_question(
        self,
        question: str,
        profile: Optional[CandidateProfile] = None,
        context: Optional[Dict[str, Any]] = None,
        similarity_threshold: float = 0.55,
        user_id: str = ""
    ) -> Tuple[Optional[str], float, Optional[VaultEntry]]:
        """High-level wrapper for dynamic question resolution."""
        ctx = context or {}
        return self.query_answer(
            question=question,
            profile=profile,
            company=ctx.get("company", ""),
            role=ctx.get("role", ""),
            domain=ctx.get("domain", ""),
            similarity_threshold=similarity_threshold,
            user_id=user_id,
            job_id=ctx.get("job_id") or None,
        )


vault = KnowledgeVault()
