"""
JobCopilot - Self-Learning Hybrid Knowledge Vault
Indexes Q&A pairs with semantic embeddings, lexical token matching,
and deterministic slot key resolution for zero-repeat autonomous form filling.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from app.core.models import VaultEntry, SlotType, CandidateProfile
from app.core.slot_matcher import SlotMatcher
from app.core.database import db


class KnowledgeVault:
    """Self-learning Knowledge Vault storing and resolving recruiter Q&As."""

    def __init__(self):
        self.matcher = SlotMatcher()
        self._ensure_baseline_entries()

    def _ensure_baseline_entries(self):
        """Seeds baseline universal recruiter questions and refreshes vector dimensions."""
        existing = db.get_all_vault_entries()
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
                self.learn_answer(question, template, slot_type=slot_type, slot_key=slot_key)
        else:
            # Refresh embeddings if vocabulary changed
            for entry in existing:
                if len(entry.embedding) != vocab_len:
                    entry.embedding = self.matcher.get_embedding(entry.question_pattern)
                    db.save_vault_entry(entry)

    def seed_from_profile(self, profile: CandidateProfile):
        """Seeds the Knowledge Vault with rich, specialized slots directly from a candidate profile."""
        prefs = profile.preferences
        notice_str = f"{prefs.notice_period_days} days" if prefs.notice_period_days > 0 else "0 days (Immediate)"

        # 1. Update Core Recruiter Preferences Slots
        self.learn_answer("What is your expected CTC / compensation?", prefs.expected_ctc, slot_type=SlotType.EXACT_PARAM, slot_key="expected_ctc")
        self.learn_answer("What is your current CTC / salary?", prefs.current_ctc, slot_type=SlotType.EXACT_PARAM, slot_key="current_ctc")
        self.learn_answer("What is your notice period / earliest start date?", notice_str, slot_type=SlotType.EXACT_PARAM, slot_key="notice_period_days")
        self.learn_answer("Are you open to relocation?", "Yes, willing to relocate" if prefs.willing_to_relocate else "No, remote only", slot_type=SlotType.EXACT_PARAM, slot_key="willing_to_relocate")
        self.learn_answer("Do you require visa sponsorship?", "Yes, require visa sponsorship" if prefs.requires_sponsorship else "No, legally authorized without sponsorship", slot_type=SlotType.EXACT_PARAM, slot_key="requires_sponsorship")

        # 2. Seed Skill-Specific Experience Slots
        yoe = prefs.years_of_experience
        for skill in profile.skills:
            self.learn_answer(
                f"How many years of experience do you have with {skill}?",
                f"{yoe:.1f} years" if yoe >= 1.0 else "1 year",
                slot_type=SlotType.TECH_YEARS,
                slot_key=f"TECH_YEARS:{skill}"
            )

        # 3. Seed Career Narrative
        if prefs.why_looking_for_role:
            self.learn_answer(
                "Why are you looking for a new role?",
                prefs.why_looking_for_role,
                slot_type=SlotType.PARAMETRIC_ESSAY,
                slot_key="why_looking_for_role"
            )

    def learn_answer(self, question: str, answer_template: str, slot_type: Optional[SlotType] = None, slot_key: Optional[str] = None) -> VaultEntry:
        """Stores or updates a Q&A slot in the Knowledge Vault."""
        if not slot_type or not slot_key:
            slot_type, slot_key = self.matcher.detect_slot_type(question)

        embedding = self.matcher.get_embedding(question)

        # Check if an entry with this slot_key already exists
        existing_entries = db.get_all_vault_entries()
        for e in existing_entries:
            if (e.slot_key == slot_key and e.slot_type == slot_type) or e.question_pattern.lower() == question.lower():
                e.answer_template = answer_template
                e.question_pattern = question
                e.embedding = embedding
                e.last_used_at = datetime.now().isoformat()
                db.save_vault_entry(e)
                return e

        entry = VaultEntry(
            qa_id=f"qa_{uuid.uuid4().hex[:8]}",
            slot_type=slot_type,
            slot_key=slot_key,
            question_pattern=question,
            embedding=embedding,
            answer_template=answer_template,
            dynamic_variables=["company", "role", "domain", "expected_ctc", "github_url", "linkedin_url"],
            usage_count=1,
            last_used_at=datetime.now().isoformat()
        )
        db.save_vault_entry(entry)
        return entry

    def _resolve_template(
        self,
        template: str,
        profile: Optional[CandidateProfile],
        company: str,
        role: str,
        domain: str
    ) -> str:
        """Substitutes dynamic template variables into final human answer."""
        resolved = template.replace("{company}", company).replace("{role}", role).replace("{domain}", domain)
        if profile:
            prefs = profile.preferences
            resolved = resolved.replace("{expected_ctc}", prefs.expected_ctc)
            resolved = resolved.replace("{current_ctc}", prefs.current_ctc)
            resolved = resolved.replace("{notice_period_days}", str(prefs.notice_period_days))
            resolved = resolved.replace("{earliest_start_date}", prefs.earliest_start_date)
            resolved = resolved.replace("{work_authorization}", prefs.work_authorization)
            resolved = resolved.replace("{sponsorship_answer}", "Yes" if prefs.requires_sponsorship else "No")
            resolved = resolved.replace("{relocation_answer}", "Yes, open to relocate" if prefs.willing_to_relocate else "No, remote only")
            resolved = resolved.replace("{remote_preference}", prefs.remote_preference)
            resolved = resolved.replace("{years_of_experience}", f"{prefs.years_of_experience:.1f}")
            resolved = resolved.replace("{top_skills}", ", ".join(profile.skills[:5]))
            resolved = resolved.replace("{full_name}", profile.full_name)
            resolved = resolved.replace("{email}", profile.email)
            resolved = resolved.replace("{phone}", profile.phone)
            resolved = resolved.replace("{location}", profile.location)
            resolved = resolved.replace("{github_url}", profile.github_url or "https://github.com")
            resolved = resolved.replace("{linkedin_url}", profile.linkedin_url or "https://linkedin.com")
        return resolved

    def query_answer(
        self,
        question: str,
        profile: Optional[CandidateProfile] = None,
        company: str = "the company",
        role: str = "Software Engineer",
        domain: str = "Technology",
        similarity_threshold: float = 0.55
    ) -> Tuple[Optional[str], float, Optional[VaultEntry]]:
        """Queries the Knowledge Vault using deterministic slot resolution and hybrid search."""
        entries = db.get_all_vault_entries()
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

        return None, best_score, None


vault = KnowledgeVault()
