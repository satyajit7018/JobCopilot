"""
JobCopilot - Advanced Mock Interview Studio & Company Architecture Dossier Generator
Generates high-frequency technical and STAR leadership questions based on real FAANG,
Stripe, Meta, Netflix, and Uber interview loops, with multi-dimensional rubric scoring.
"""

import re
from typing import List, Dict, Any, Optional


class InterviewStudioEngine:
    """Simulates realistic technical interviews and evaluates engineering depth."""

    COMPANY_PROFILES = {
        "stripe": {
            "likely_tech_stack": ["Ruby", "Java / Go", "Sorbet", "PostgreSQL", "Kafka", "Redis", "AWS / Envoy", "Spinnaker"],
            "engineering_focus": "Extreme financial correctness, idempotent payment ledgers, double-entry bookkeeping, multi-region high availability, and developer-first API design.",
            "common_interview_rounds": [
                "Round 1: 45-min Bug Hunter & Code Refactoring in your language of choice",
                "Round 2: 60-min Distributed System Design (Idempotency, Ledgers, Rate Limiting)",
                "Round 3: 60-min Integration & API Design (SDK contracts & failure recovery)",
                "Round 4: 45-min Technical Leadership, Disagreements & Product Intuition"
            ],
            "key_preparation_tips": [
                "Focus on failure-as-default semantics: explain how to handle retries without double-charging using Idempotency-Keys.",
                "Discuss double-entry ledgers where every debit strictly matches a credit with immutable audit trails.",
                "Compare rate limiting algorithms: Token Bucket vs Leaky Bucket vs Sliding Window Logs in Redis."
            ]
        },
        "uber": {
            "likely_tech_stack": ["Go", "Java", "Python", "H3 Spatial Index", "Kafka", "Schemaless / MySQL", "Jaeger", "Kubernetes"],
            "engineering_focus": "High-throughput real-time geospatial location ingestion, ride-matching algorithms, dynamic pricing, and sub-second dispatch latency.",
            "common_interview_rounds": [
                "Round 1: 45-min Live Coding (Algorithms & Concurrent Data Structures)",
                "Round 2: 60-min System Design (Real-Time Driver Location & Dispatch Architecture)",
                "Round 3: 60-min Distributed Systems & Storage (Partitioning, Consensus & Raft)",
                "Round 4: 45-min Uber Norms & Bar Raiser Behavioral Evaluation"
            ],
            "key_preparation_tips": [
                "Explain geospatial partitioning using H3 Hexagonal Hierarchical Spatial Indexing or Quadtrees.",
                "Discuss how to handle WebSocket connection spikes from millions of concurrent mobile drivers.",
                "Demonstrate how you design for partial network disconnects and state synchronization."
            ]
        },
        "netflix": {
            "likely_tech_stack": ["Java / Spring Boot", "Node.js", "Python", "gRPC", "Apache Cassandra", "Kafka", "AWS / Titus", "Chaos Monkey"],
            "engineering_focus": "Global content delivery network (Open Connect), adaptive bitrate video streaming, recommendation engines, and automated chaos engineering.",
            "common_interview_rounds": [
                "Round 1: 45-min Technical Phone Screen (Microservices Architecture)",
                "Round 2: 60-min Video Streaming Architecture & Global CDN Caching",
                "Round 3: 60-min Distributed Data Modeling (Cassandra Wide-Column & Consistency)",
                "Round 4: 60-min Culture of Freedom & Responsibility Deep Dive"
            ],
            "key_preparation_tips": [
                "Discuss adaptive bitrate streaming (HLS/DASH) and video manifest chunking strategies.",
                "Explain resilience patterns: Circuit Breakers, Bulkheads, and fallback caches.",
                "Align with the Netflix Culture Memo: high performance, context over control, and extreme autonomy."
            ]
        },
        "meta": {
            "likely_tech_stack": ["C++", "Python", "Hack / PHP", "Rust", "GraphQL", "TAO (Graph DB)", "Cassandra", "RocksDB", "Buck"],
            "engineering_focus": "Massive scale (3B+ users), graph database traversal, real-time feed ranking, live video streaming, and rapid iteration under ambiguous constraints.",
            "common_interview_rounds": [
                "Round 1 & 2: 45-min Coding Rounds (Data Structures, Graphs & DP)",
                "Round 3: 45-min System Design (News Feed, Instagram Stories, or Live Comments)",
                "Round 4: 45-min Behavioral & Leadership (Moving Fast, Resolving Conflict & Growth)"
            ],
            "key_preparation_tips": [
                "Master Fan-out on Write vs Fan-out on Read trade-offs for high-follower celebrity accounts.",
                "Explain multi-tier caching with Memcached / Redis and graph cache invalidation.",
                "Emphasize the 'Move Fast' philosophy: ship vertical MVPs, measure impact, and iterate."
            ]
        }
    }

    MASTER_QUESTIONS = [
        # Category 1: System Design & Scalability
        {
            "id": "q_sys_stripe_1",
            "category": "System Design",
            "company_tag": "Stripe",
            "difficulty": "Hard",
            "question": "How would you design a distributed payment ledger and idempotency engine that guarantees zero double-billing across network retries at 100,000 TPS?",
            "key_concepts": ["Idempotency-Key Header", "Double-Entry Ledger", "Distributed Lock (Redis Lua)", "Compensating Transactions", "Atomic State Machine", "P99 SLA"],
            "sample_star": "At my previous fintech role, payment retry storms caused duplicate authorizations during gateway outages. I architected an idempotency middleware storing client keys in Redis with an atomic Lua script distributed lock. Successful charges were written to an immutable double-entry PostgreSQL ledger where debits strictly matched credits. Unfinished requests returned cached payloads. This eliminated duplicate transactions across 80M monthly payments and lowered P99 latency to 42ms."
        },
        {
            "id": "q_sys_uber_2",
            "category": "System Design",
            "company_tag": "Uber",
            "difficulty": "Hard",
            "question": "How would you design a high-throughput geospatial ingestion pipeline to track millions of concurrent driver locations and calculate nearest-driver dispatch in real-time?",
            "key_concepts": ["H3 Spatial Indexing", "Geohash / Quadtree", "WebSocket Gateway", "Redis Pub/Sub & Sorted Sets", "Dispatch Matcher", "Backpressure"],
            "sample_star": "Our fleet tracking platform experienced severe lag when processing GPS pings from 150k vehicles. I introduced an H3 hexagonal indexing pipeline with a WebSocket cluster terminating TLS at Envoy edge proxies. Location pings were partitioned into Redis Geospatial indices with a 15-second TTL. The dispatch matching engine queried adjacent H3 rings in O(1) time, cutting match latency from 3.2s to 120ms and handling 100k writes/sec seamlessly."
        },
        {
            "id": "q_sys_netflix_3",
            "category": "System Design",
            "company_tag": "Netflix",
            "difficulty": "Hard",
            "question": "Design a global content delivery infrastructure and video transcoding pipeline capable of serving adaptive bitrate streaming to 200 million users during live events.",
            "key_concepts": ["Edge CDN Caching", "Adaptive Bitrate (HLS/DASH)", "Transcoding Workers", "S3 Blob Storage", "Circuit Breaker", "Simian Chaos"],
            "sample_star": "We needed to broadcast live events to 2M concurrent viewers without buffering. I built an automated transcoding pipeline using asynchronous worker clusters that segmented MP4 video into multi-bitrate HLS chunks uploaded to S3. We configured global Cloudflare CDN edge caching with proactive pre-fetching of video manifests. When regional CDN nodes failed, automated circuit breakers rerouted traffic, maintaining a 99.98% stream availability."
        },
        {
            "id": "q_sys_meta_4",
            "category": "System Design",
            "company_tag": "Meta",
            "difficulty": "Hard",
            "question": "How would you design a real-time social feed with personalized ranking for users with millions of followers (handling the celebrity fan-out problem)?",
            "key_concepts": ["Fan-out on Write vs Read", "Hybrid Feed Pipeline", "Redis Tiered Cache", "Graph Database (TAO)", "Ranking Model Inference", "Kafka Stream"],
            "sample_star": "In our social app, posting from verified creators with >1M followers overwhelmed our database fan-out queue. I redesigned the feed with a hybrid model: regular users used fan-out on write, while high-follower accounts used fan-out on read with lazy client-side feed merging. We cached personalized timelines in Redis Cluster and ranked posts with an async inference service, reducing timeline load times by 78%."
        },

        # Category 2: Concurrency & Database Internals
        {
            "id": "q_con_rate_5",
            "category": "Architecture & Concurrency",
            "company_tag": "Universal",
            "difficulty": "Medium",
            "question": "How would you implement a distributed rate limiter supporting sliding window counters across multiple microservice regions without clock drift vulnerabilities?",
            "key_concepts": ["Sliding Window Logs", "Redis Sorted Sets (ZADD/ZREMRANGE)", "Atomic Lua Scripts", "Fail-Open vs Fail-Closed", "Memory Eviction"],
            "sample_star": "To prevent API abuse on our public endpoints, I built a distributed sliding window rate limiter using Redis sorted sets. Each request executed an atomic Lua script that removed expired timestamps, added the current timestamp, and checked card against quota in a single round-trip. We implemented a fail-open circuit breaker to guarantee availability if Redis degraded. The service handled 40,000 req/sec with < 2ms latency."
        },
        {
            "id": "q_con_db_6",
            "category": "Architecture & Concurrency",
            "company_tag": "Universal",
            "difficulty": "Hard",
            "question": "Under heavy concurrent database write contention, how do you diagnose and eliminate database connection pool exhaustion and deadlocks?",
            "key_concepts": ["Optimistic Concurrency Control", "Connection Pool Sizing", "AsyncIO Event Loop", "Read Replicas & Sharding", "WAL Checkpoints"],
            "sample_star": "During a flash sale, our primary PostgreSQL instance reached 100% connection pool exhaustion with rampant row-level deadlocks. I diagnosed lock contention using pg_stat_activity and reorganized transaction statements to acquire row locks in deterministic order. I replaced pessimistic locks with optimistic concurrency using version tokens, moved read traffic to read replicas with PgBouncer connection pooling, reducing CPU from 98% to 34%."
        },

        # Category 3: Incident Response & Chaos Engineering
        {
            "id": "q_inc_thundering_7",
            "category": "Incident Response",
            "company_tag": "Universal",
            "difficulty": "Hard",
            "question": "Describe an incident involving a cascading failure or cache stampede (thundering herd) that you investigated. How did you stabilize production and prevent recurrence?",
            "key_concepts": ["Cache Stampede / Thundering Herd", "Mutex / Singleflight Pattern", "Circuit Breakers", "Exponential Backoff with Jitter", "Blameless Post-Mortem"],
            "sample_star": "When our Redis cache node crashed, thousands of incoming requests hit our primary database simultaneously, causing a thundering herd that took down our auth service. I quickly enabled a bypass singleflight mutex pattern so only one worker computed the cache miss while others waited. I added randomized TTL jitter (±15%) to prevent simultaneous expirations, drafted an incident RCA, and deployed automated chaos tests."
        },

        # Category 4: Executive STAR Leadership & Behavioral
        {
            "id": "q_lead_conflict_8",
            "category": "STAR Leadership",
            "company_tag": "FAANG",
            "difficulty": "Medium",
            "question": "Tell me about a high-stakes technical disagreement you had with a Principal Engineer or Manager regarding architecture. How did you navigate it to a successful outcome?",
            "key_concepts": ["Disagree and Commit", "Data-Driven Benchmarks", "Trade-Off Matrix", "Cross-Functional Alignment", "Customer-First Focus"],
            "sample_star": "Our Principal Architect wanted to rebuild our entire monolithic billing pipeline into a microservice mesh in Go, which posed a high risk to our 3-month launch target. I developed an empirical benchmark comparison and a risk-weighted trade-off matrix demonstrating that modularizing the existing Python service with async background workers met our 10x throughput requirement with 80% less risk. We aligned, delivered 2 weeks early, and scaled to $20M ARR without outage."
        },
        {
            "id": "q_lead_ambiguity_9",
            "category": "STAR Leadership",
            "company_tag": "FAANG",
            "difficulty": "Medium",
            "question": "Describe a project where you had to deliver critical technical outcomes under tight deadlines with highly ambiguous or frequently shifting product requirements.",
            "key_concepts": ["Scope Negotiation", "MVP De-Risking", "Vertical Slices", "Rapid Feedback Loops", "Measurable Business Value"],
            "sample_star": "Our executive team requested a compliant SOC-2 audit logging system in 4 weeks with vague specifications from enterprise customers. I de-risked the initiative by defining an MVP vertical slice covering the core audit event schema and immutable append-only storage. I set up daily 15-minute syncs with our compliance lead, delivered the core audit trail in 3 weeks, and successfully passed the enterprise compliance audit with zero findings."
        }
    ]

    @classmethod
    def generate_company_dossier(cls, company_name: str, role_title: str) -> Dict[str, Any]:
        """Generates tailored architecture insights, tech stack, and round breakdowns for any company."""
        comp_clean = company_name.strip()
        comp_key = comp_clean.lower()
        role_clean = role_title.strip()

        profile = cls.COMPANY_PROFILES.get(comp_key)
        if profile:
            return {
                "company": comp_clean,
                "role": role_clean,
                "likely_tech_stack": profile["likely_tech_stack"],
                "engineering_focus": profile["engineering_focus"],
                "common_interview_rounds": profile["common_interview_rounds"],
                "key_preparation_tips": profile["key_preparation_tips"]
            }

        # Dynamic synthesis for any other company
        return {
            "company": comp_clean,
            "role": role_clean,
            "likely_tech_stack": ["Python / Go / TypeScript", "FastAPI / gRPC / Next.js", "PostgreSQL / DynamoDB", "Redis Cluster", "Kafka / SQS", "Docker & Kubernetes", "AWS / GCP"],
            "engineering_focus": f"Scalable distributed systems, high-throughput microservices, sub-100ms API latency, and bulletproof reliability tailored for {comp_clean}'s core domain.",
            "common_interview_rounds": [
                "Round 1: 30-min Recruiter Screen & High-Level Experience Overview",
                "Round 2: 60-min Data Structures, Concurrency & Problem Solving",
                "Round 3: 60-min Distributed System Design & Architectural Scalability",
                "Round 4: 45-min Engineering Leadership, Conflict Resolution & STAR Behavioral"
            ],
            "key_preparation_tips": [
                f"Prepare concrete quantitative examples: emphasize latency reductions, throughput numbers (RPS/TPS), and system reliability.",
                f"Deeply understand {comp_clean}'s core business model and the primary engineering bottlenecks in their architecture.",
                "Structure all responses using the STAR method: Situation (20%), Task (10%), Action (50%), Result (20%)."
            ]
        }

    @classmethod
    def generate_mock_questions(
        cls,
        role_title: str = "Senior Software Engineer",
        skills: Optional[List[str]] = None,
        seniority: str = "Senior",
        category: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Returns tailored questions or master questions bank based on category."""
        if category and category.lower() != "all":
            filtered = [q for q in cls.MASTER_QUESTIONS if q["category"].lower() == category.lower()]
            if filtered:
                return filtered
        elif category and category.lower() == "all":
            return cls.MASTER_QUESTIONS

        # When called with custom skills (e.g. in targeted tests or specific tailoring)
        if skills:
            target_skills = skills or ["Python", "Distributed Systems"]
            top_skill = target_skills[0] if target_skills else "Python"
            sec_skill = target_skills[1] if len(target_skills) > 1 else "FastAPI"
            return [
                {
                    "id": "q_sys_1",
                    "category": "System Design",
                    "question": "How would you design a real-time event streaming and notification pipeline handling 50,000 requests per second with at-least-once delivery guarantees?",
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
                    "question": "Describe a situation where a critical production outage occurred or a technical decision caused a bottleneck. How did you diagnose, resolve, and prevent recurrence?",
                    "key_concepts": ["Root Cause Analysis (RCA)", "Observability / Metrics", "Zero-Downtime Rollback", "Blameless Post-Mortem"],
                    "difficulty": "Medium"
                }
            ]

        return cls.MASTER_QUESTIONS

    @classmethod
    def evaluate_interview_response(
        cls,
        question: str,
        key_concepts: Optional[List[str]] = None,
        candidate_answer: str = ""
    ) -> Dict[str, Any]:
        """Evaluates verbal or written response with multi-dimensional STAR scoring and metrics verification."""
        text = candidate_answer.strip()
        concepts = key_concepts or ["Idempotency", "Concurrency", "Partitioning", "P99 Latency", "Observability"]

        if len(text) < 20:
            return {
                "score": 35,
                "overall_score": 35,
                "rating": "Needs Detail",
                "hire_verdict": "Needs Detail 🛠️",
                "concepts_covered_ratio": f"0 / {len(concepts)}",
                "dimension_scores": {"situation": 25, "action": 30, "result": 20, "delivery": 35},
                "covered_concepts": [],
                "matched_concepts": [],
                "missing_concepts": concepts,
                "has_metrics": False,
                "feedback": "Your response is too brief. Provide a structured STAR explanation with specific architectural decisions, concrete tools, and quantitative results."
            }

        covered = []
        missing = []
        text_lower = text.lower()

        # Semantic concept match
        for c in concepts:
            keywords = [w.lower() for w in re.findall(r'[a-zA-Z0-9]+', c) if len(w) > 2]
            if any(k in text_lower for k in keywords):
                covered.append(c)
            else:
                missing.append(c)

        # Check for quantitative metrics (numbers, ms, %, req/s, TPS, etc.)
        has_metrics = bool(re.search(r'\b\d+(\.\d+)?\s*(ms|s|%|k|m|rps|tps|req|x|users|gb|mb|\$)\b', text_lower) or re.search(r'\b\d{2,}\b', text))

        coverage_ratio = len(covered) / max(len(concepts), 1)

        # Calculate dimension scores
        situation_score = min(100, int(60 + (25 if any(w in text_lower for w in ["problem", "outage", "challenge", "spike", "legacy", "bottleneck", "needed"]) else 0) + (15 if len(text) > 80 else 0)))
        action_score = min(100, int(50 + (coverage_ratio * 40) + (10 if any(w in text_lower for w in ["architected", "built", "implemented", "designed", "introduced", "configured", "partition", "use"]) else 0)))
        result_score = min(100, int(50 + (30 if has_metrics else 10) + (20 if any(w in text_lower for w in ["reduced", "improved", "eliminated", "scaled", "achieved", "delivered", "ensure", "tracking"]) else 0)))
        delivery_score = min(100, int(70 + (20 if 40 <= len(text.split()) <= 250 else 10) + (10 if not any(w in text_lower for w in ["um", "uh", "maybe", "i guess"]) else 0)))

        overall_score = max(int((situation_score * 0.25) + (action_score * 0.35) + (result_score * 0.25) + (delivery_score * 0.15)), int(50 + (coverage_ratio * 45)))

        if overall_score >= 80:
            rating = "Excellent"
            verdict = "Strong Hire 🚀"
            feedback = "Outstanding technical depth. Strong articulation of architectural trade-offs, failure recovery, and quantitative impact."
        elif overall_score >= 65:
            rating = "Proficient"
            verdict = "Hire 👍"
            feedback = f"Solid answer with good technical foundation. To elevate to Strong Hire, explicitly address: {', '.join(missing[:2])}."
        elif overall_score >= 50:
            rating = "Developing"
            verdict = "Leaning Hire ⚖️"
            feedback = f"Good start, but missing key architectural depth. Address critical mechanisms like: {', '.join(missing)} and quantify your business impact."
        else:
            rating = "Needs Detail"
            verdict = "Needs Work 🛠️"
            feedback = "Lacks concrete technical mechanisms and measurable outcomes. Structure your answer strictly around Situation, Task, Action, and Result."

        return {
            "score": overall_score,
            "overall_score": overall_score,
            "rating": rating,
            "hire_verdict": verdict,
            "concepts_covered_ratio": f"{len(covered)} / {len(concepts)}",
            "dimension_scores": {
                "situation": situation_score,
                "action": action_score,
                "result": result_score,
                "delivery": delivery_score
            },
            "covered_concepts": covered,
            "matched_concepts": covered,
            "missing_concepts": missing,
            "has_metrics": has_metrics,
            "feedback": feedback
        }

    @classmethod
    def evaluate_candidate_response(
        cls,
        question: str,
        candidate_answer: str,
        key_concepts: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Convenience alias for evaluate_interview_response."""
        return cls.evaluate_interview_response(
            question=question,
            candidate_answer=candidate_answer,
            key_concepts=key_concepts
        )
