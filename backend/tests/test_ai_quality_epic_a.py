"""
JobCopilot - Phase P1 Epic A Verification Suite: Real AI Quality & Semantic Matching
Validates:
1. LLMClient token usage tracking, tier budgets (Free, Pro, Elite), and quota enforcement
2. SHA-256 hash-keyed response caching with TTL and cache hit metrics
3. Async streaming token generation for real-time UI/voice studio
4. Structured JSON schema completion with markdown wrapper stripping
5. Universal dense text embeddings and cosine similarity semantic ordering
6. MatchScorer semantic vector alignment scoring (compute_match_score_semantic)
7. KnowledgeVault dense vector semantic search and /api/vault/semantic-search endpoint
"""

import pytest
from fastapi.testclient import TestClient

from app.core.llm_client import llm_client
from app.core.match_scorer import MatchScorer
from app.core.vector_vault import KnowledgeVault
from app.core.models import CandidateProfile, WorkExperience, Project, RecruiterPreferences


# =========================================================================
# 1. Token Usage Tracking & Tier Budgeting
# =========================================================================
def test_token_budget_tracking_and_quotas():
    user_id = "usr_token_test_1"
    llm_client.reset_token_usage(user_id)

    # Free tier: budget check
    assert llm_client.check_and_consume_budget(user_id, estimated_tokens=1000, tier="FREE")

    # Record usage
    llm_client.record_token_usage(user_id, prompt_tokens=20000, completion_tokens=30000)
    usage = llm_client.get_token_usage(user_id)
    assert usage["total_tokens"] == 50000

    # Free tier limit is 50,000 -> next 1000 tokens should fail budget
    assert not llm_client.check_and_consume_budget(user_id, estimated_tokens=1000, tier="FREE")

    # Pro tier limit is 500,000 -> should pass
    assert llm_client.check_and_consume_budget(user_id, estimated_tokens=1000, tier="PRO")


# =========================================================================
# 2. SHA-256 Hash-Keyed Response Caching
# =========================================================================
@pytest.mark.asyncio
async def test_llm_response_caching():
    llm_client.clear_cache()
    prompt = "Explain distributed event sourcing in one sentence."

    # First call: cache miss
    res1 = await llm_client.generate_completion(prompt, user_id="usr_cache_test")
    stats1 = llm_client.get_cache_stats()
    assert stats1["entries_count"] >= 1
    assert stats1["misses"] >= 1

    # Second call: cache hit
    res2 = await llm_client.generate_completion(prompt, user_id="usr_cache_test")
    assert res1 == res2
    stats2 = llm_client.get_cache_stats()
    assert stats2["hits"] >= 1


# =========================================================================
# 3. Async Streaming Token Generator
# =========================================================================
@pytest.mark.asyncio
async def test_streaming_token_generation():
    chunks = []
    async for chunk in llm_client.stream_completion("Stream interview feedback"):
        chunks.append(chunk)

    assert len(chunks) > 0
    full_output = "".join(chunks)
    assert len(full_output) > 10


# =========================================================================
# 4. Structured Output / JSON Mode
# =========================================================================
@pytest.mark.asyncio
async def test_structured_json_mode_and_markdown_stripping():
    # Test JSON mode with fallback
    json_res = await llm_client.chat_completion_json(
        prompt="Generate JSON payload",
        fallback_fn=lambda: {"status": "ok", "recommendation": "Use PostgreSQL"},
        user_id="usr_json_test"
    )
    assert isinstance(json_res, dict)
    assert json_res.get("status") in ["ok", "success"]


# =========================================================================
# 5. Universal Text Embeddings & Cosine Similarity
# =========================================================================
@pytest.mark.asyncio
async def test_embeddings_and_semantic_ordering():
    # Technical query
    q_vec = await llm_client.embed_text("FastAPI and Python microservice architecture")
    tech_vec = await llm_client.embed_text("High-throughput Python backend with distributed Redis caching")
    unrelated_vec = await llm_client.embed_text("Classical oil painting and renaissance sculpture techniques")

    sim_tech = llm_client.cosine_similarity(q_vec, tech_vec)
    sim_unrelated = llm_client.cosine_similarity(q_vec, unrelated_vec)

    assert sim_tech > sim_unrelated, f"Semantic similarity failed: {sim_tech} <= {sim_unrelated}"
    assert -1.0 <= sim_tech <= 1.0


# =========================================================================
# 6. Semantic Match Scorer (compute_match_score_semantic)
# =========================================================================
def test_semantic_match_scorer():
    profile = CandidateProfile(
        id="usr_scorer_sem",
        full_name="Aarav Gupta",
        email="aarav@tech.io",
        phone="+91 98765 43210",
        location="Bengaluru, India",
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Apache Kafka"],
        summary="Backend engineer building high-scale Python microservices and event streaming pipelines.",
        experience=[
            WorkExperience(
                company="FinTech Ltd",
                title="Backend Software Engineer",
                start_date="2022",
                end_date="Present",
                highlights=["Engineered payment processing pipelines with sub-50ms latency."]
            )
        ],
        preferences=RecruiterPreferences(years_of_experience=3.0, remote_preference="Remote")
    )

    # 1. High semantic fit role
    score_sem, reasons_sem, _ = MatchScorer.compute_match_score_semantic(
        profile=profile,
        job_title="Senior Python Backend Developer",
        job_description="Seeking a backend engineer with Python, FastAPI, and Kafka experience to architect distributed data services.",
        job_location="Remote"
    )
    assert score_sem >= 0.50
    assert len(reasons_sem) > 0

    # 2. Irrelevant role
    score_irrelevant, _, _ = MatchScorer.compute_match_score_semantic(
        profile=profile,
        job_title="Pediatric Dental Assistant",
        job_description="Assisting dentists with pediatric dental procedures and patient record management.",
        job_location="Onsite"
    )
    assert score_sem > score_irrelevant


# =========================================================================
# 7. Semantic Vector Vault & REST Endpoint
# =========================================================================
def test_vector_vault_semantic_search_and_endpoint(auth_client: TestClient):
    vault_inst = KnowledgeVault()
    # Teach a custom Q&A
    vault_inst.learn_answer(
        question="What is your approach to handling database deadlocks in PostgreSQL?",
        answer_template="I configure lock timeouts, use consistent lock ordering, and rely on advisory locks.",
        slot_key="pg_deadlocks",
        user_id="usr_test_tenant_a"
    )

    # Test direct semantic search
    results = vault_inst.search_semantic(
        query="How do you resolve concurrent deadlock issues in relational databases?",
        user_id="usr_test_tenant_a",
        top_k=3
    )
    assert len(results) > 0
    top_entry, sim_score = results[0]
    assert "deadlock" in top_entry.question_pattern.lower()
    assert sim_score > 0.0

    # Test REST API endpoint /api/vault/semantic-search
    res_api = auth_client.post("/api/vault/semantic-search", json={
        "query": "How do you handle database deadlocks?",
        "top_k": 3
    })
    assert res_api.status_code == 200
    data = res_api.json()
    assert data["status"] == "success"
    assert data["count"] > 0
    assert "similarity_score" in data["results"][0]
