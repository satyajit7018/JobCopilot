"""
JobCopilot - Self-Learning Hybrid Knowledge Vault
Indexes Q&A pairs with semantic embeddings, lexical token matching,
and deterministic slot key resolution for zero-repeat autonomous form filling.
"""

import re
import uuid
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

# Answers about one company ("Why do you want to work here?") are never reused for another.
COMPANY_SPECIFIC_KEYS = {"why_join_company"}

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
                "Why are you looking for a new role?",
                reason,
                slot_type=SlotType.PARAMETRIC_ESSAY,
                slot_key="why_looking_for_role",
                user_id=profile.user_id or "default",
            )

    def learn_answer(
        self,
        question: str,
        answer_template: str,
        slot_type: Optional[SlotType] = None,
        slot_key: Optional[str] = None,
        user_id: str = "default"
    ) -> VaultEntry:
        """Stores or updates a Q&A slot in the Knowledge Vault for user."""
        if not slot_type or not slot_key:
            slot_type, slot_key = self.matcher.detect_slot_type(question)

        embedding = self.matcher.get_embedding(question)

        # Check if an entry with this slot_key already exists for this user
        existing_entries = self._get_entries(user_id=user_id)
        for e in existing_entries:
            if (e.slot_key == slot_key and e.slot_type == slot_type) or e.question_pattern.lower() == question.lower():
                e.slot_key = slot_key
                e.slot_type = slot_type
                e.answer_template = answer_template
                e.question_pattern = question
                e.embedding = embedding
                e.last_used_at = datetime.now().isoformat()
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
            last_used_at=datetime.now().isoformat()
        )
        db.save_vault_entry(entry, user_id=user_id)
        return entry

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

    def query_answer(
        self,
        question: str,
        profile: Optional[CandidateProfile] = None,
        company: str = "",
        role: str = "",
        domain: str = "",
        similarity_threshold: float = 0.55,
        user_id: str = ""
    ) -> Tuple[Optional[str], float, Optional[VaultEntry]]:
        """The user's answer to an application question, or (None, score, None).

        Answers come only from the user: profile fields they have saved, or answers they gave
        before. A question about a known topic (salary, notice period, years with one skill) is
        answered from that topic or not at all, never from a question that merely looks similar.
        """
        target_user = user_id or (profile.user_id if profile else "")
        entries = self._own_entries(target_user)

        # 1. A known topic.
        detected_type, detected_key = self.matcher.detect_slot_type(question)
        if detected_key != "general_question":
            if detected_key in COMPANY_SPECIFIC_KEYS:
                return None, 0.0, None
            if detected_key in PROFILE_SLOTS and profile is not None:
                resolved = self._resolve_template(PROFILE_SLOTS[detected_key], profile, company, role, domain)
                if resolved:
                    return resolved, 1.0, None
            for entry in entries:
                if entry.slot_key == detected_key and entry.slot_type == detected_type:
                    resolved = self._resolve_template(entry.answer_template, profile, company, role, domain)
                    if resolved:
                        db.increment_vault_usage(entry.qa_id)
                        return resolved, 1.0, entry
            return None, 0.0, None

        # 2. Anything else: the user's own earlier answer to a similar question.
        reusable = [e for e in entries if e.slot_key not in COMPANY_SPECIFIC_KEYS]
        query_embedding = self.matcher.get_embedding(question)
        best_entry = None
        best_score = 0.0
        for entry in reusable:
            doc_emb = entry.embedding
            if len(doc_emb) != len(query_embedding):
                doc_emb = self.matcher.get_embedding(entry.question_pattern)
            score = self.matcher.compute_hybrid_score(question, query_embedding, entry.question_pattern, doc_emb)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= similarity_threshold:
            resolved = self._resolve_template(best_entry.answer_template, profile, company, role, domain)
            if resolved:
                db.increment_vault_usage(best_entry.qa_id)
                return resolved, best_score, best_entry

        # 3. Dense semantic search over the same answers.
        for top_sem_entry, top_sem_score in self.search_semantic(question, user_id=target_user, top_k=1):
            if top_sem_score >= similarity_threshold and top_sem_entry.slot_key not in COMPANY_SPECIFIC_KEYS:
                resolved = self._resolve_template(top_sem_entry.answer_template, profile, company, role, domain)
                if resolved:
                    db.increment_vault_usage(top_sem_entry.qa_id)
                    return resolved, top_sem_score, top_sem_entry

        return None, best_score, None

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
            user_id=user_id
        )


vault = KnowledgeVault()
