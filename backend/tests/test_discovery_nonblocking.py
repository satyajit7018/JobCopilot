"""
Discovery must not freeze the API.

POST /api/discovery/run used to score thousands of leads directly on the event
loop (~40s with live feeds), so every other request, including /auth/me,
stalled until the search finished. Scoring now runs in a worker thread, and the
two hot spots (skill matching and SimHash) were made faster without changing
their output; the reference implementations below pin that.
"""

import asyncio
import hashlib
import re
import time
from collections import Counter

from app.core.deduplicator import JobDeduplicator
from app.core.match_scorer import MatchScorer
from app.core.models import CandidateProfile
from app.core.resume_parser import ResumeParser
from app.discovery.orchestrator import DiscoveryOrchestrator

SAMPLES = [
    "",
    "python",
    "Senior Python engineer: Django, FastAPI, PostgreSQL, Redis, AWS and Docker.",
    "We use JavaScript (not Java), TypeScript, React Native and React. C++ / C# a plus. Go or Golang, R, Scala.",
    "Machine learning with PyTorch & TensorFlow; Kubernetes on GCP; CI/CD via GitHub Actions. " * 20,
    "Rust rust RUST — résumé ünïcode — node.js, Node, NodeJS, .NET, SQL/NoSQL, HTML5 + CSS3.",
]


def _reference_simhash(text: str) -> int:
    """The original bit-by-bit SimHash."""
    if not text:
        return 0
    words = re.findall(r'\b\w+\b', text.lower())
    if not words:
        return 0
    shingles = [f"{words[i]} {words[i+1]}" for i in range(len(words) - 1)] if len(words) >= 2 else words
    v = [0] * 64
    for shingle, weight in Counter(shingles).items():
        h = int(hashlib.md5(shingle.encode('utf-8')).hexdigest()[:16], 16)
        for i in range(64):
            v[i] += weight if (h >> i) & 1 else -weight
    fingerprint = 0
    for i in range(64):
        if v[i] > 0:
            fingerprint |= (1 << i)
    return fingerprint


def _reference_skills(text: str):
    """The original regex-per-skill matcher."""
    text_lower = text.lower()
    buckets, all_skills = {}, []
    for category, skills in ResumeParser.SKILL_TAXONOMY.items():
        bucket = []
        for skill in skills:
            if re.search(r'(?<!\w)' + re.escape(skill.lower()) + r'(?!\w)', text_lower):
                bucket.append(skill)
                if skill not in all_skills:
                    all_skills.append(skill)
        buckets[category] = bucket
    return all_skills, buckets


def test_simhash_matches_reference():
    for text in SAMPLES:
        assert JobDeduplicator.compute_simhash_64(text) == _reference_simhash(text), text[:40]


def test_categorize_skills_matches_reference():
    for text in SAMPLES:
        all_skills, categorized = ResumeParser.categorize_skills(text)
        ref_all, ref_buckets = _reference_skills(text)
        assert all_skills == ref_all
        for category, bucket in ref_buckets.items():
            assert getattr(categorized, category) == bucket


def test_discovery_scoring_does_not_block_event_loop(monkeypatch):
    orchestrator = DiscoveryOrchestrator()

    async def no_network(_companies):
        return [{"company": "Acme", "title": "Engineer"}]

    def slow_score(**_kwargs):
        time.sleep(1.0)  # stands in for scoring thousands of leads
        return 0.0, [], []

    monkeypatch.setattr(orchestrator, "_fetch_all_raw_leads", no_network)
    monkeypatch.setattr(MatchScorer, "compute_match_score", staticmethod(slow_score))
    profile = CandidateProfile(full_name="T", email="t@example.com", phone="0", location="Remote")

    async def scenario():
        ticks = 0

        async def ticker():
            nonlocal ticks
            while True:
                await asyncio.sleep(0.05)
                ticks += 1

        tick_task = asyncio.create_task(ticker())
        result = await orchestrator.run_discovery_cycle(profile, user_id="u1")
        tick_task.cancel()
        return result, ticks

    result, ticks = asyncio.run(scenario())
    assert result["status"] == "success"
    assert result["total_sourced"] == 1
    # A blocked loop would tick at most once during the 1s of scoring.
    assert ticks >= 10
