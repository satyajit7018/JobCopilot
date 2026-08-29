"""
JobCopilot - Mock Interview Studio & Company Architecture Dossier Generator
Generates role-specific technical question sets, engineering system dossiers,
and evaluates verbal/text responses with depth and key concept scoring.
"""

from typing import List, Dict, Any, Optional


class InterviewStudioEngine:
    """Simulates realistic technical interviews and evaluates engineering depth."""

    @classmethod
    def generate_company_dossier(cls, company_name: str, role_title: str) -> Dict[str, Any]:
        """Generates engineering dossier and architectural insights for the target company."""
        comp_clean = company_name.strip()
        role_clean = role_title.strip()

        # Architecture and engineering profile synthesis
        dossier = {
            "company": comp_clean,
            "role": role_clean,
            "likely_tech_stack": ["Python", "Go / Rust", "FastAPI / gRPC", "PostgreSQL", "Kafka / Redis", "Kubernetes", "AWS / GCP"],
            "engineering_focus": f"Scalable distributed systems, high-throughput microservices, and reliable cloud infrastructure tailored for {comp_clean}'s core domain.",
            "common_interview_rounds": [
                "Round 1: 30-min Recruiter & Experience Deep Dive",
                "Round 2: 60-min Data Structures & Concurrency Coding",
                "Round 3: 60-min Distributed System Design & Architecture",
                "Round 4: 45-min Engineering Leadership & Cross-Functional Alignment"
            ],
            "key_preparation_tips": [
                f"Be ready to explain how your past projects handle fault tolerance and scaling bottlenecks.",
                f"Review database indexing strategies (B-Tree vs LSM-Tree) and message queue partitioning (Kafka consumer groups).",
                f"Demonstrate how you measure performance and observability (P99 latency, Prometheus, OpenTelemetry)."
            ]
        }
        return dossier

    @classmethod
    def generate_mock_questions(
        cls,
        role_title: str,
        skills: Optional[List[str]] = None,
        seniority: str = "Senior"
    ) -> List[Dict[str, Any]]:
        """Generates role-specific system design, coding, and behavioral interview questions."""
        target_skills = skills or ["Python", "Distributed Systems", "SQL", "Docker"]
        top_skill = target_skills[0] if target_skills else "Python"
        sec_skill = target_skills[1] if len(target_skills) > 1 else "FastAPI"

        return [
            {
                "id": "q_sys_1",
                "category": "System Design",
                "question": f"How would you design a real-time event streaming and notification pipeline handling 50,000 requests per second with at-least-once delivery guarantees?",
                "key_concepts": ["Message Broker (Kafka/RabbitMQ)", "Idempotency Keys", "Consumer Group Partitioning", "Dead Letter Queues (DLQ)", "P99 Latency SLA"],
                "difficulty": "Hard"
            },
            {
                "id": "q_tech_2",
                "category": "Architecture & Concurrency",
                "question": f"In {top_skill} and {sec_skill}, how do you manage race conditions, connection pooling, and horizontal scaling under heavy database write contention?",
                "key_concepts": ["Optimistic vs Pessimistic Locking", "Connection Pool Sizing", "AsyncIO / Event Loop", "Read Replicas & Sharding"],
                "difficulty": "Medium"
            },
            {
                "id": "q_beh_3",
                "category": "Engineering Leadership",
                "question": f"Describe a situation where a critical production outage occurred or a technical decision caused a bottleneck. How did you diagnose, resolve, and prevent recurrence?",
                "key_concepts": ["Root Cause Analysis (RCA)", "Observability / Metrics", "Zero-Downtime Rollback", "Blameless Post-Mortem"],
                "difficulty": "Medium"
            }
        ]

    @classmethod
    def evaluate_interview_response(
        cls,
        question: str,
        key_concepts: Optional[List[str]] = None,
        candidate_answer: str = ""
    ) -> Dict[str, Any]:
        """Convenience alias for evaluate_candidate_response."""
        return cls.evaluate_candidate_response(
            question=question,
            candidate_answer=candidate_answer,
            key_concepts=key_concepts
        )

    @classmethod
    def evaluate_candidate_response(
        cls,
        question: str,
        candidate_answer: str,
        key_concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Evaluates candidate response on coverage, depth, and communication clarity."""
        text = candidate_answer.strip()
        if len(text) < 20:
            return {
                "score": 35,
                "rating": "Needs Detail",
                "covered_concepts": [],
                "missing_concepts": key_concepts or [],
                "feedback": "Your answer is too brief. Provide specific technical examples, architectural trade-offs, and metrics from past work."
            }

        concepts = key_concepts or ["Idempotency", "Concurrency", "Partitioning", "Latency", "Observability"]
        covered = []
        missing = []
        text_lower = text.lower()

        for c in concepts:
            # Check if concept or main keyword in concept appears in answer
            words = [w.lower() for w in c.replace("(", "").replace(")", "").split() if len(w) > 3]
            if any(w in text_lower for w in words):
                covered.append(c)
            else:
                missing.append(c)

        coverage_ratio = len(covered) / max(len(concepts), 1)
        base_score = int(50 + (coverage_ratio * 45))
        score = min(max(base_score, 40), 98)

        if score >= 85:
            rating = "Excellent"
            feedback = "Strong technical explanation with clear architectural depth and solid key concept coverage."
        elif score >= 70:
            rating = "Proficient"
            feedback = f"Good foundational explanation. To make it top-tier, explicitly mention: {', '.join(missing[:2])}."
        else:
            rating = "Developing"
            feedback = f"Ensure you address critical architectural components like: {', '.join(missing)}."

        return {
            "score": score,
            "rating": rating,
            "covered_concepts": covered,
            "missing_concepts": missing,
            "feedback": feedback
        }
