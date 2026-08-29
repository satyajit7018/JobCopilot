"""
JobCopilot - Self-Learning Knowledge Vault
Indexes Q&A pairs with semantic embeddings for zero-repeat question filling.
"""

import uuid
from datetime import datetime
from typing import Optional, List, Dict, Tuple
from app.core.models import VaultEntry, SlotType, CandidateProfile
from app.core.slot_matcher import SlotMatcher
from app.core.database import db


class KnowledgeVault:
    def __init__(self):
        self.matcher = SlotMatcher()
        self._ensure_baseline_entries()

    def _ensure_baseline_entries(self):
        existing = db.get_all_vault_entries()
        if existing:
            return

        # Pre-populate baseline universal recruiter Q&As
        baselines = [
            ("What is your expected salary / CTC?", SlotType.EXACT_PARAM, "expected_ctc", "{expected_ctc}"),
            ("What is your current CTC?", SlotType.EXACT_PARAM, "current_ctc", "{current_ctc}"),
            ("What is your notice period?", SlotType.EXACT_PARAM, "notice_period_days", "{notice_period_days} days (Immediate)"),
            ("Are you authorized to work in this location?", SlotType.EXACT_PARAM, "work_authorization", "Yes, fully authorized without visa sponsorship required."),
            ("Are you willing to relocate?", SlotType.EXACT_PARAM, "willing_to_relocate", "Yes, open to relocation and hybrid/on-site working arrangements."),
            ("Why do you want to work at our company?", SlotType.PARAMETRIC_ESSAY, "why_join_company", 
             "I am deeply excited about {company}'s work in {domain}. With hands-on experience in building scalable Python backends, machine learning pipelines, and vector search systems, I am eager to contribute immediately to {company}'s product engineering goals."),
            ("Share a link to an AI or technical project you built.", SlotType.PARAMETRIC_ESSAY, "technical_achievement",
             "I built a high-throughput Multimodal Diagnostic AI system utilizing PyTorch and FastAPI with sub-50ms latency and 96.19% classification accuracy. GitHub repository and documentation available at: {github_url}")
        ]

        for question, slot_type, slot_key, template in baselines:
            self.learn_answer(question, template, slot_type=slot_type, slot_key=slot_key)

    def learn_answer(self, question: str, answer_template: str, slot_type: Optional[SlotType] = None, slot_key: Optional[str] = None) -> VaultEntry:
        if not slot_type or not slot_key:
            slot_type, slot_key = self.matcher.detect_slot_type(question)

        embedding = self.matcher.get_embedding(question)
        entry = VaultEntry(
            qa_id=f"qa_{uuid.uuid4().hex[:8]}",
            slot_type=slot_type,
            slot_key=slot_key,
            question_pattern=question,
            embedding=embedding,
            answer_template=answer_template,
            dynamic_variables=["company", "role", "domain", "expected_ctc", "github_url"],
            usage_count=1,
            last_used_at=datetime.now().isoformat()
        )
        db.save_vault_entry(entry)
        return entry

    def query_answer(self, question: str, profile: Optional[CandidateProfile] = None, company: str = "the company", role: str = "Software Engineer", domain: str = "Technology", similarity_threshold: float = 0.70) -> Tuple[Optional[str], float, Optional[VaultEntry]]:
        query_embedding = self.matcher.get_embedding(question)
        entries = db.get_all_vault_entries()
        if not entries:
            return None, 0.0, None

        best_entry = None
        best_score = 0.0

        for entry in entries:
            score = self.matcher.cosine_similarity(query_embedding, entry.embedding)
            if score > best_score:
                best_score = score
                best_entry = entry

        if best_entry and best_score >= similarity_threshold:
            # Increment usage count
            best_entry.usage_count += 1
            best_entry.last_used_at = datetime.now().isoformat()
            db.save_vault_entry(best_entry)

            # Resolve template parameters
            template = best_entry.answer_template
            resolved = template.replace("{company}", company).replace("{role}", role).replace("{domain}", domain)
            if profile:
                resolved = resolved.replace("{expected_ctc}", profile.preferences.expected_ctc)
                resolved = resolved.replace("{current_ctc}", profile.preferences.current_ctc)
                resolved = resolved.replace("{notice_period_days}", str(profile.preferences.notice_period_days))
                resolved = resolved.replace("{github_url}", profile.github_url or "https://github.com")

            return resolved, best_score, best_entry

        return None, best_score, None


vault = KnowledgeVault()
