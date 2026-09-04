"""
JobCopilot - Self-Learning Hybrid Knowledge Vault
Indexes Q&A pairs with semantic embeddings, lexical token matching,
and deterministic slot key resolution for zero-repeat autonomous form filling.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Tuple, Any
from app.core.models import VaultEntry, SlotType, CandidateProfile
from app.core.slot_matcher import SlotMatcher
from app.core.database import db


class KnowledgeVault:
    """Self-learning Knowledge Vault storing and resolving recruiter Q&As with in-memory caching."""

    def __init__(self):
        self.matcher = SlotMatcher()
        self._cached_entries: Optional[List[VaultEntry]] = None
        self._ensure_baseline_entries()

    def _get_entries(self, user_id: str = "system_baseline") -> List[VaultEntry]:
        """Retrieves cached vault entries or reads from database for user."""
        return db.get_vault_entries(user_id=user_id)

    def _ensure_baseline_entries(self):
        """Seeds baseline universal recruiter questions and refreshes vector dimensions."""
        existing = db.get_vault_entries(user_id="system_baseline")
        vocab_len = len(self.matcher.VOCABULARY)

        baselines = [
            ("What is your expected salary / CTC?", SlotType.EXACT_PARAM, "expected_ctc", "{expected_ctc}"),
            ("What is your current CTC / salary?", SlotType.EXACT_PARAM, "current_ctc", "{current_ctc}"),
            ("What is your notice period or earliest start date?", SlotType.EXACT_PARAM, "notice_period_days", "{notice_period_days} days ({earliest_start_date})"),
            ("Are you legally authorized to work in this location?", SlotType.EXACT_PARAM, "work_authorization", "{work_authorization}"),
            ("Do you require visa sponsorship now or in the future?", SlotType.EXACT_PARAM, "requires_sponsorship", "{sponsorship_answer}"),
            ("Are you willing to relocate for this role?", SlotType.EXACT_PARAM, "willing_to_relocate", "{relocation_answer}"),
            ("What is your preferred work arrangement (Remote / Hybrid / On-site)?", SlotType.EXACT_PARAM, "remote_preference", "{remote_preference}"),
            ("Total years of professional engineering experience?", SlotType.EXACT_PARAM, "years_of_experience", "{years_of_experience} years"),
            ("Why do you want to work at our company?", SlotType.PARAMETRIC_ESSAY, "why_join_company", 
             "I am excited about {company}'s focus on {domain}. With experience in building scalable Python backends, machine learning pipelines, and vector search systems, I am eager to contribute directly to {company}'s engineering goals."),
            ("Why should we hire you for this role?", SlotType.PARAMETRIC_ESSAY, "why_hire_me",
             "I bring strong hands-on experience in {top_skills} combined with a track record of delivering high-performance software. I thrive in collaborative, fast-paced environments and take full ownership of backend reliability and feature delivery."),
            ("Share a link to a technical project you built.", SlotType.PARAMETRIC_ESSAY, "technical_achievement",
             "I developed a high-throughput diagnostic AI system with FastAPI and PyTorch achieving 96.19% classification accuracy and sub-50ms latency. Documentation and code available at: {github_url}")
        ]

        if not existing:
            for question, slot_type, slot_key, template in baselines:
                self.learn_answer(question, template, slot_type=slot_type, slot_key=slot_key, user_id="system_baseline")
        else:
            # Refresh embeddings if vocabulary changed
            for entry in existing:
                if len(entry.embedding) != vocab_len:
                    entry.embedding = self.matcher.get_embedding(entry.question_pattern)
                    db.save_vault_entry(entry, user_id="system_baseline")

    def seed_from_profile(self, profile: CandidateProfile):
        """Seeds the Knowledge Vault with rich, specialized slots directly from a candidate profile."""
        prefs = profile.preferences
        notice_str = f"{prefs.notice_period_days} days" if prefs.notice_period_days > 0 else "0 days (Immediate)"
        uid = profile.user_id or "default"

        # 1. Update Core Recruiter Preferences Slots
        self.learn_answer("What is your expected CTC / compensation?", prefs.expected_ctc, slot_type=SlotType.EXACT_PARAM, slot_key="expected_ctc", user_id=uid)
        self.learn_answer("What is your current CTC / salary?", prefs.current_ctc, slot_type=SlotType.EXACT_PARAM, slot_key="current_ctc", user_id=uid)
        self.learn_answer("What is your notice period / earliest start date?", notice_str, slot_type=SlotType.EXACT_PARAM, slot_key="notice_period_days", user_id=uid)
        self.learn_answer("Are you open to relocation?", "Yes, willing to relocate" if prefs.willing_to_relocate else "No, remote only", slot_type=SlotType.EXACT_PARAM, slot_key="willing_to_relocate", user_id=uid)
        self.learn_answer("Do you require visa sponsorship?", "Yes, require visa sponsorship" if prefs.requires_sponsorship else "No, legally authorized without sponsorship", slot_type=SlotType.EXACT_PARAM, slot_key="requires_sponsorship", user_id=uid)

        # 2. Seed Skill-Specific Experience Slots
        yoe = prefs.years_of_experience
        for skill in profile.skills:
            self.learn_answer(
                f"How many years of experience do you have with {skill}?",
                f"{yoe:.1f} years" if yoe >= 1.0 else "1 year",
                slot_type=SlotType.TECH_YEARS,
                slot_key=f"TECH_YEARS:{skill}",
                user_id=uid
            )

        # 3. Seed Career Narrative
        if prefs.why_looking_for_role:
            self.learn_answer(
                "Why are you looking for a new role?",
                prefs.why_looking_for_role,
                slot_type=SlotType.PARAMETRIC_ESSAY,
                slot_key="why_looking_for_role",
                user_id=uid
            )

    def learn_question(self, question: str, answer: str, **kwargs) -> VaultEntry:
        """Alias for learn_answer."""
        return self.learn_answer(question=question, answer_template=answer, **kwargs)

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

    def _resolve_template(
        self,
        template: str,
        profile: Optional[CandidateProfile],
        company: str,
        role: str,
        domain: str
    ) -> str:
        """Substitutes dynamic template variables into final human answer with strict null-safety."""
        resolved = (template or "").replace("{company}", str(company or "the company")).replace("{role}", str(role or "Software Engineer")).replace("{domain}", str(domain or "Technology"))
        if profile:
            prefs = profile.preferences
            expected_ctc = str(getattr(prefs, "expected_ctc", "") or "15 LPA")
            current_ctc = str(getattr(prefs, "current_ctc", "") or "12 LPA")
            notice_days = str(getattr(prefs, "notice_period_days", 0) or 0)
            earliest_date = str(getattr(prefs, "earliest_start_date", "") or "Immediate")
            work_auth = str(getattr(prefs, "work_authorization", "") or "Authorized")
            req_spon = bool(getattr(prefs, "requires_sponsorship", False))
            open_reloc = bool(getattr(prefs, "willing_to_relocate", False))
            remote_pref = str(getattr(prefs, "remote_preference", "") or "Remote")
            yoe = float(getattr(prefs, "years_of_experience", 0.0) or 0.0)
            skills = profile.skills if isinstance(profile.skills, list) else []
            top_skills = ", ".join(str(s) for s in skills[:5]) if skills else "Python, FastAPI, Backend Systems"

            resolved = resolved.replace("{expected_ctc}", expected_ctc)
            resolved = resolved.replace("{current_ctc}", current_ctc)
            resolved = resolved.replace("{notice_period_days}", notice_days)
            resolved = resolved.replace("{earliest_start_date}", earliest_date)
            resolved = resolved.replace("{work_authorization}", work_auth)
            resolved = resolved.replace("{sponsorship_answer}", "Yes" if req_spon else "No")
            resolved = resolved.replace("{relocation_answer}", "Yes, open to relocate" if open_reloc else "No, remote only")
            resolved = resolved.replace("{remote_preference}", remote_pref)
            resolved = resolved.replace("{years_of_experience}", f"{yoe:.1f}")
            resolved = resolved.replace("{top_skills}", top_skills)
            resolved = resolved.replace("{full_name}", str(profile.full_name or "Candidate"))
            resolved = resolved.replace("{email}", str(profile.email or ""))
            resolved = resolved.replace("{phone}", str(profile.phone or ""))
            resolved = resolved.replace("{location}", str(profile.location or "Remote"))
            resolved = resolved.replace("{github_url}", str(profile.github_url or "https://github.com"))
            resolved = resolved.replace("{linkedin_url}", str(profile.linkedin_url or "https://linkedin.com"))
        return resolved

    def query_answer(
        self,
        question: str,
        profile: Optional[CandidateProfile] = None,
        company: str = "the company",
        role: str = "Software Engineer",
        domain: str = "Technology",
        similarity_threshold: float = 0.55,
        user_id: str = ""
    ) -> Tuple[Optional[str], float, Optional[VaultEntry]]:
        """Queries the Knowledge Vault using deterministic slot resolution and hybrid search."""
        target_user = user_id or (profile.user_id if profile else "system_baseline")
        
        user_entries = self._get_entries(user_id=target_user) if target_user != "system_baseline" else []
        baseline_entries = self._get_entries(user_id="system_baseline")
        
        # User overrides take precedence over universal system baselines
        user_keys = {e.slot_key for e in user_entries if e.slot_key}
        entries = list(user_entries) + [b for b in baseline_entries if b.slot_key not in user_keys]
        
        if not entries:
            return None, 0.0, None

        # 1. Deterministic Slot Matching
        detected_type, detected_key = self.matcher.detect_slot_type(question)
        if detected_key != "general_question":
            for entry in entries:
                if entry.slot_key == detected_key and entry.slot_type == detected_type:
                    db.increment_vault_usage(entry.qa_id)
                    resolved = self._resolve_template(entry.answer_template, profile, company, role, domain)
                    return resolved, 1.0, entry

        # 2. Hybrid Semantic + Lexical Search Fallback
        query_embedding = self.matcher.get_embedding(question)
        best_entry = None
        best_score = 0.0

        for entry in entries:
            doc_emb = entry.embedding
            if len(doc_emb) != len(query_embedding):
                doc_emb = self.matcher.get_embedding(entry.question_pattern)

            score = self.matcher.compute_hybrid_score(question, query_embedding, entry.question_pattern, doc_emb)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= similarity_threshold:
            db.increment_vault_usage(best_entry.qa_id)
            resolved = self._resolve_template(best_entry.answer_template, profile, company, role, domain)
            return resolved, best_score, best_entry

        # 3. Dense Semantic Vector Retrieval Fallback
        semantic_matches = self.search_semantic(question, user_id=target_user, top_k=1)
        if semantic_matches:
            top_sem_entry, top_sem_score = semantic_matches[0]
            if top_sem_score >= similarity_threshold:
                db.increment_vault_usage(top_sem_entry.qa_id)
                resolved = self._resolve_template(top_sem_entry.answer_template, profile, company, role, domain)
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

        user_entries = self._get_entries(user_id=user_id) if user_id != "system_baseline" else []
        baseline_entries = self._get_entries(user_id="system_baseline")
        user_keys = {e.slot_key for e in user_entries if e.slot_key}
        entries = list(user_entries) + [b for b in baseline_entries if b.slot_key not in user_keys]

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
            company=ctx.get("company", "the company"),
            role=ctx.get("role", "Software Engineer"),
            domain=ctx.get("domain", "Technology"),
            similarity_threshold=similarity_threshold,
            user_id=user_id
        )


vault = KnowledgeVault()
