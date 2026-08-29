# JobCopilot: Production Architecture & Implementation Plan

**Universal Autonomous Job Hunting, Self-Learning Application & Career Operating System**

---

## 1. System Overview

JobCopilot is a local-first, autonomous multi-ATS application platform. It discovers new job openings, generates tailored PDF resumes matching specific role requirements, auto-fills and submits application forms with human-like browser interaction, reaches out to hiring managers directly, indexes novel questions via a real-time HITL bridge, and tracks interview pipelines.

```mermaid
flowchart TD
    subgraph S1 [1. Onboarding & Storage]
        A[Upload Resume PDF/Docx] --> B[Universal Resume Parser]
        B --> C[Pre-filled Recruiter Questionnaire]
        C --> D[Seed Hybrid Vector Vault]
        D --> DB[(SQLite WAL Mode + Argon2id Keyring)]
    end

    subgraph S2 [2. Job Discovery]
        D1[Greenhouse / Lever / Ashby APIs]
        D2[VC Portals: Sequoia, a16z, YC & HN Hiring Threads]
        D3[Scrapers: Wellfound, Naukri, Indeed]
        D1 & D2 & D3 --> FitScorer[Multi-Factor Resume Match Scorer]
        FitScorer --> Dedup[64-bit SimHash Deduplicator]
    end

    subgraph S3 [3. Tailoring & Generation]
        Dedup --> Tailor[Per-Job Tailored PDF Resume Engine]
        Tailor --> CoverLetter[Human-Tone Cover Letter Generator]
        CoverLetter --> SkillGap[Skill Gap Analyzer & Market Comp Predictor]
    end

    subgraph S4 [4. Browser Automation]
        ContextPool[Chromium BrowserContext Pool]
        StealthCDP[CDP Evasion: Zero webdriver leaks]
        Physics[Bézier Mouse Curves + Digraph Typing Jitter]
        EdgeSolvers[Honeypot Bypass + Canvas Signatures + Combobox Solvers]
        Adapters[7+ ATS Adapters + Self-Healing Selectors]
        DryRun[Side-by-Side Dry Run Screenshot Simulator]
    end

    subgraph S5 [5. Self-Learning HITL Bridge]
        HITL_FSM[Atomic HITL State Machine + Timeout Fallback]
        Telegram[Telegram Bot 1-Click Mobile Companion]
        WebAlert[Web Dashboard Live Modal with Human-Draft Answer]
    end

    subgraph S6 [6. Multi-Channel Outreach]
        O1[Channel 1: ATS Form Submission]
        O2[Channel 2: Direct LinkedIn Connection Note]
        O3[Channel 3: Direct Cold Email to Engineering Lead]
    end

    subgraph S7 [7. Status Tracking & Interview Prep]
        IMAP[IMAP IDLE Push Real-Time Email Monitor]
        Calendar[Calendar Availability & Scheduling Engine]
        MockStudio[AI Mock Interview Studio & Scoring]
        CompNegotiator[Levels.fyi Benchmarks & Offer Negotiation Drafter]
    end

    subgraph S8 [8. Web Dashboard]
        DashboardUI[Funnel KPIs + Time-Saved Tracker]
        MiniBrowserUI[Picture-in-Picture Live Bot Stream]
        KanbanCRM[Interactive Kanban Application Board]
        VaultUI[Searchable Knowledge Vault with 1-Click Rollback]
    end

    S1 --> S2 --> S3 --> S4
    S4 -->|Known Fields| S6
    S4 -->|Novel Question| S5
    S5 -->|User Approves & Saves| S1
    S5 --> S6
    S6 --> S7
    S8 <--> S4 & S5 & S7
```

---

## 2. Core Authenticity Engine (Anti-AI Text & Behavioral Stealth)

To guarantee that no submission, cover letter, or outreach message appears machine-generated, the platform enforces strict authenticity rules across both text and browser behavior:

### A. Zero-AI Text Generation Rules
- **Banned Cliché Dictionary**: The text generator strictly strips and forbids AI markers: `delve`, `testament`, `tapestry`, `beacon`, `pivotal`, `spearheaded`, `seamless`, `utilize`, `furthermore`, `in conclusion`, `passionate about`, `thrilled to apply`.
- **Engineering-First Voice**: Sentences are direct, active, and grounded in concrete technical details, numbers, architecture choices, and measurable results.
- **Dynamic Syntax Variance**: Alternates sentence length (short punchy statements mixed with technical descriptions) to achieve natural perplexity and burstiness matching experienced human writers.
- **Context-Specific Personalization**: References actual technical challenges specific to the target company's business model rather than generic praise.

### B. Natural Behavioral Mechanics
- **Cubic Bézier Trajectories**: Mouse movements use variable acceleration, deceleration curves, and minor overshoots that correct before clicking.
- **Digraph Inter-Key Latency Matrix**: Common letter combinations (e.g. `th`, `er`, `in`) type at 35–55ms; capital letters, special characters, and rare digraphs type at 110–170ms.
- **Simulated Typo Correction**: Introduces a realistic 1% chance of hitting an adjacent keyboard character followed by a brief pause and backspace correction.
- **Poisson Schedule Jitter**: Distributes application submissions naturally over standard local business hours (9:30 AM – 5:30 PM).

---

## 3. Parallel AI Workforce Matrix

- **Executive Overseer**: **Claude Opus** (Architecture, quality gates, and integration sign-off)
- **Parallel AI Worker Squads**:
  1. **Squad A (Storage & Onboarding)**: SQLite WAL engine, Argon2id encryption, resume parser, and smart recruiter questionnaire.
  2. **Squad B (AI Core & Resume Tailoring)**: Gemini 1.5 Flash structured schemas, dynamic PDF resume compiler, hybrid RRF vector vault, and Skill Gap Analyzer.
  3. **Squad C (Platform Auth & Session Manager)**: 1-click Chrome cookie importer, assisted 2FA/CAPTCHA modal, and stealth employer blacklist.
  4. **Squad D (0-Day Discovery & Sourcing)**: Direct ATS REST APIs (Greenhouse, Lever, Ashby), VC portfolio scrapers (Sequoia, a16z, YC), and HackerNews parser.
  5. **Squad E (Stealth Browser Automation)**: Chromium `BrowserContext` pool, CDP evasion, cubic Bézier physics, digraph typing jitter, honeypot bypass, canvas digital signatures, and 7+ ATS adapters.
  6. **Squad F (Outreach & HITL Bridge)**: Typed JSON-RPC WebSocket gateway, atomic HITL FSM, Telegram mobile companion, and LinkedIn InMail + cold email generators.
  7. **Squad G (Email & Interview Studio)**: Real-time IMAP IDLE push listener, Voice AI mock interview practice studio, and Levels.fyi offer negotiation matrix.
  8. **Squad H (Frontend Dashboard & DevOps)**: React 18 + Vite dashboard, picture-in-picture mini-browser viewport, Kanban CRM, mock ATS fixture server, Docker Compose, and `start.sh`.

---

## 4. The 8 Production Milestones

---

### Milestone 1: Data Architecture, Storage & 2-Minute Smart Onboarding
- **Database Engine (`backend/app/core/database.py`)**: SQLite in WAL mode (`PRAGMA journal_mode = WAL;`), connection pooling, and zero-dependency transactional schema migrations (`_schema_versions`).
- **Argon2id + AES-256-GCM Encryption (`backend/app/core/credential_vault.py`)**: Master password derived via Argon2id ($m=64\text{MB}, t=3, p=4$) and stored in OS Keychain (`keyring`). Field-level AES-256-GCM encryption for PII (phone, email, compensation).
- **Universal Resume Parser (`backend/app/core/resume_parser.py`)**: Extracts structured skills, experience, education, projects, certifications, and social links from PDF/DOCX.
- **Smart Recruiter Questionnaire (`backend/app/core/questionnaire.py`)**: Auto-extracts 70% of questionnaire answers for 30-second user confirmation, seeding base slots into the Knowledge Vault:
  - Multi-currency salary slider (INR, USD, EUR, GBP)
  - Notice period, work authorization, relocation, remote preferences
  - YoE per skill, authentic career narrative with voice-to-text.

---

### Milestone 2: AI Engine, Hybrid Vector Search & Resume Tailoring
- **Gemini AI Service (`backend/app/core/gemini_service.py`)**: Structured Pydantic JSON mode, low-latency (< 400ms) context compression, strict anti-AI tone filters, and factuality guardrails.
- **Dynamic Resume Tailoring (`backend/app/core/resume_manager.py`)**: Contextual synonym alignment and in-memory compilation of tailored PDF resumes matching the specific job description via native Chromium CSS Paged Media (`page.pdf()`).
- **Hybrid Vector Vault (`backend/app/core/vector_vault.py`)**: Reciprocal Rank Fusion (RRF) combining dense 768-dim embeddings with lexical BM25 token matching; online slot clustering ($\ge 0.88$ cosine similarity); pure-Python/NumPy local fallback.
- **Multi-Factor Match Scorer (`backend/app/core/match_scorer.py`)**: Skills (40%), Seniority (20%), Compensation (20%), Location (10%), Company Tier (10%) with visual "Why You Match" breakdown.
- **SimHash Deduplication (`backend/app/core/deduplicator.py`)**: 64-bit SimHash identifying identical postings across different ATS domains.
- **Skill Gap Analyzer (`backend/app/core/skill_gap.py`)**: Analyzes market demand and predicts salary boosts for missing skills.

---

### Milestone 3: Platform Authentication, Session Manager & Stealth Mode
- **Chrome Profile Session Importer (`backend/app/bot/session_manager.py`)**: 1-click active session cookie import from local Chrome/Brave profile without typing credentials.
- **Interactive Assisted Sign-In Modal**: Spawns a visible browser window for 2FA, OTP, or CAPTCHAs, saving authenticated cookies permanently.
- **Stealth Mode Filter**: Automatically detects and blacklists the candidate's current employer, sister companies, subsidiaries, and corporate recruiters.

---

### Milestone 4: 0-Day Job Discovery & Sourcing Engine
- **Direct ATS REST APIs (`backend/app/discovery/ats_apis.py`)**: High-speed JSON endpoints for Greenhouse, Lever, and Ashby (500+ jobs in < 2s via `httpx` async HTTP/2 connection pooling).
- **VC Portfolio & HackerNews Sourcing (`backend/app/discovery/vc_sourcing.py`)**: Sourcing from **Sequoia Capital**, **a16z**, **YC Directory**, **HN "Who is Hiring?"**, **Wellfound**, **Naukri**, and **Indeed**.
- **0-Day Velocity Filter**: Prioritizes jobs posted in the last 2 hours.
- **Asset & Tracker Blocker**: Blocks images, fonts, video, and analytics scripts during discovery for 65% faster page loads.

---

### Milestone 5: Autonomous Multi-ATS Playwright Worker Pool & Anti-Bot Engine
- **BrowserContext Pool (`backend/app/bot/worker_pool.py`)**: Master Chromium process with lightweight context isolation (< 50ms startup, ~30MB RAM/worker), dynamic memory autoscaling, and asynchronous `ProcessReaper`.
- **CDP Stealth & Humanizer (`backend/app/bot/humanizer.py`)**: CDP evasion scripts (masks `navigator.webdriver`, mocks WebGL, aligns `Sec-CH-UA`), cubic Bézier mouse curves with Gaussian velocity, and digraph inter-key latency model with typo/backspace simulation.
- **Edge-Case & Anti-Trap Solvers (`backend/app/bot/adapters/base_adapter.py`)**:
  - Honeypot form field detection and bypass
  - Canvas / SVG cursive digital signature generator
  - Async autocomplete combobox search dropdown solver
  - Post-submission confirmation receipt scraper & screenshot archiver
- **Specialized Platform Adapters**: `GreenhouseAdapter`, `LeverAdapter`, `AshbyAdapter`, `WorkdayAdapter`, `YCWellfoundAdapter`, and `GenericATSAdapter`.
- **Interactive Dry-Run Simulator (`backend/app/bot/dry_run.py`)**: Side-by-side screenshot preview showing proposed answers without submitting.

---

### Milestone 6: Multi-Channel Outreach & Self-Learning HITL Bridge
- **Triple-Threat Multi-Channel Outreach (`backend/app/bot/outreach.py`)**:
  - Channel 1: Stealth ATS form auto-submission
  - Channel 2: Tailored 280-character LinkedIn InMail / Connection note to hiring manager
  - Channel 3: Direct 3-sentence cold email to engineering lead.
- **Typed JSON-RPC WebSocket Gateway (`backend/app/api/ws_gateway.py`)**: RPC protocol with correlation IDs (`msg_id`) and heartbeat keepalive frames.
- **Atomic HITL State Machine (`backend/app/bot/hitl_bridge.py`)**: `PENDING` $\to$ `NOTIFIED` $\to$ `RESOLVED` $\to$ `COMMITTED` with human-voice AI draft suggestions and safe timeout auto-draft fallback.
- **Telegram Bot Mobile Companion (`backend/app/bot/telegram_companion.py`)**: Push notifications with inline action buttons (`[ Approve ]`, `[ Edit ]`, `[ Skip ]`).

---

### Milestone 7: Real-Time Email Intelligence, Voice Mock Studio & Salary Negotiation
- **IMAP IDLE Push Email Monitor (`backend/app/core/email_monitor.py`)**: Real-time zero-polling push listener via `aioimaplib` and Gmail OAuth2 with honeypot tracking pixel neutralization.
- **Zero-Collision Calendar Scheduling**: Computes candidate free/busy slots on Google/Outlook calendar and highlights non-conflicting interview times.
- **Voice Mock Interview Studio (`backend/app/core/interview_studio.py`)**: Voice-enabled practice sessions with role-specific technical/system design questions and scoring feedback.
- **Salary Negotiation & Offer Modeler (`backend/app/core/negotiation.py`)**: Levels.fyi compensation benchmarks, startup ESOP equity modeler, and realistic counter-offer negotiation scripts.

---

### Milestone 8: React Dashboard, Turnkey Deployment & Disaster Recovery
- **FastAPI Unified Backend (`backend/app/main.py` & `backend/app/api/`)**: Complete REST API and WebSocket gateway with OpenTelemetry-compatible structured JSON logging.
- **React 18 + Vite Web Dashboard (`frontend/src/`)**:
  - `OnboardingWizard.jsx`: 2-minute resume upload & prefilled questionnaire.
  - `MiniBrowserViewport.jsx`: Picture-in-picture live bot stream.
  - `Dashboard.jsx`: Funnel metrics, active workers, ROI time-saved counter, skill gap widget.
  - `JobPipeline.jsx`: Priority queue, 0-day target packs, "Why You Match" breakdown, Dry-Run preview.
  - `KanbanCRM.jsx`: Drag-and-drop job tracking CRM.
  - `BotConsole.jsx`: Real-time terminal log viewer and emergency pause/stop controls.
  - `HITLModal.jsx`: 1-Click "Approve & Learn" modal with AI draft diffing.
  - `KnowledgeVault.jsx`: Searchable QA vault with revision history and 1-click rollback.
  - `InterviewStudioModal.jsx`: Voice Mock Interview Studio & Company Dossier.
  - `OfferNegotiatorModal.jsx`: ESOP & salary counter-offer tool.
- **Disaster Recovery & 1-Click Launcher**: Encrypted archive export/import (`.jobcopilot.enc`), `docker-compose.yml`, and turnkey `start.sh`.

---

## 5. Master Codebase Directory Layout

```
JobCopilot/
├── PLAN.md                           # Master Architecture & Implementation Plan
├── docker-compose.yml                # Multi-container orchestration recipe
├── start.sh                          # Turnkey one-click launcher
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── test_phase1.py
│   ├── tests/
│   │   ├── fixtures/
│   │   │   └── mock_ats_server.py    # Mock ATS server for offline CI
│   │   ├── test_core.py              # Parser, Questionnaire & Vault tests
│   │   ├── test_api.py               # REST & JSON-RPC WebSocket tests
│   │   ├── test_discovery.py         # Direct API & scraper tests
│   │   ├── test_adapters.py          # Playwright ATS form-filling tests
│   │   ├── test_hitl.py              # HITL FSM & timeout tests
│   │   ├── test_outreach.py          # Multi-channel outreach tests
│   │   └── test_email.py             # IMAP IDLE & NLP intent tests
│   └── app/
│       ├── main.py                       # FastAPI entrypoint & lifespan
│       ├── core/
│       │   ├── config.py                 # Environment & configuration
│       │   ├── database.py               # SQLite WAL engine & migrations
│       │   ├── models.py                 # Pydantic schemas (Typed models)
│       │   ├── resume_parser.py          # Universal resume parser
│       │   ├── questionnaire.py          # Recruiter questionnaire & prefill
│       │   ├── resume_manager.py         # Dynamic per-job resume tailoring
│       │   ├── vector_vault.py           # Hybrid RRF Knowledge Vault
│       │   ├── gemini_service.py         # AI service with strict authenticity filters
│       │   ├── match_scorer.py           # Multi-factor fit scorer & SimHash
│       │   ├── priority_ranker.py        # Priority queue ranker
│       │   ├── skill_gap.py              # Skill gap analyzer & ROI predictor
│       │   ├── outcome_learner.py        # Adaptive outcome learning
│       │   ├── deduplicator.py           # Cross-platform deduplicator
│       │   ├── compensation.py           # Multi-currency CTC converter
│       │   ├── credential_vault.py       # Argon2id + AES-256 session storage
│       │   ├── email_monitor.py          # IMAP IDLE scanner & NLP tracker
│       │   ├── interview_studio.py       # Voice mock interview simulator
│       │   ├── negotiation.py            # Offer evaluation & counter-offer engine
│       │   └── logger.py                 # Structured OpenTelemetry JSON logger
│       ├── api/
│       │   ├── router.py                 # Unified API router
│       │   ├── profile_api.py        # Resume upload & questionnaire
│       │   ├── auth_manager_api.py       # Assisted sign-in & session health
│       │   ├── jobs_api.py               # Job queue, discovery & dry-run
│       │   ├── discovery_api.py          # 0-day target packs & API sourcing
│       │   ├── vault_api.py              # Knowledge vault CRUD & tester
│       │   ├── hitl_api.py               # Live question approval
│       │   ├── bot_api.py                # Worker pool control & stream
│       │   ├── outreach_api.py           # Multi-channel outreach manager
│       │   ├── email_api.py              # Email sync & interview prep
│       │   ├── stats_api.py              # Analytics & ROI time-saved
│       │   ├── health_api.py             # System diagnostic check
│       │   └── ws_gateway.py             # Typed JSON-RPC WebSocket gateway
│       ├── discovery/
│       │   ├── ats_apis.py               # Direct Greenhouse / Lever / Ashby APIs
│       │   ├── vc_sourcing.py            # Sequoia, a16z, YC & HN sourcing
│       │   ├── scrapers/                 # YC, Wellfound, Naukri, Indeed scrapers
│       │   ├── rate_limiter.py           # Token bucket per-domain throttler
│       │   └── pipeline.py               # Quality filter & ingestion pipeline
│       └── bot/
│           ├── worker_pool.py            # BrowserContext multi-worker pool
│           ├── session_manager.py        # Chrome cookie import & assisted 2FA
│           ├── humanizer.py              # Bézier mouse & digraph keystroke jitter
│           ├── checkpoint.py             # In-flight step checkpointing
│           ├── dry_run.py                # Visual screenshot preview generator
│           ├── hitl_bridge.py            # HITL atomic FSM & timeout bridge
│           ├── outreach.py               # Direct InMail & cold email engine
│           ├── telegram_companion.py     # Telegram bot companion
│           └── adapters/
│               ├── base_adapter.py       # Base ATS, honeypots & canvas signatures
│               ├── greenhouse.py         # Greenhouse adapter
│               ├── lever.py              # Lever adapter
│               ├── ashby.py              # Ashby adapter
│               ├── workday.py            # Workday adapter
│               ├── yc_wellfound.py       # YC & Wellfound adapter
│               └── generic.py            # Heuristic universal solver
└── frontend/
    ├── Dockerfile
    ├── index.html
    ├── package.json
    ├── vite.config.js
    └── src/
        ├── main.jsx
        ├── App.jsx
        ├── index.css                     # Dark/light design system
        ├── components/
        │   ├── Navbar.jsx
        │   ├── NotificationCenter.jsx
        │   ├── StatCard.jsx
        │   ├── MiniBrowserViewport.jsx   # Live picture-in-picture bot screen
        │   ├── LiveLogViewer.jsx         # Real-time terminal log viewer
        │   ├── JobCard.jsx               # Job card with 'Why You Match' breakdown
        │   ├── HITLModal.jsx             # 1-Click "Approve & Learn" modal
        │   ├── DryRunModal.jsx           # Side-by-side auto-fill preview modal
        │   ├── AuthManagerModal.jsx      # Assisted login & session manager
        │   ├── InterviewStudioModal.jsx  # Voice mock interview simulator
        │   ├── OfferNegotiatorModal.jsx  # ESOP & salary counter-offer tool
        │   └── OnboardingWizard.jsx      # 2-Min resume upload & prefilled form
        ├── pages/
        │   ├── Dashboard.jsx             # Funnel metrics, ROI stats & skill gap
        │   ├── JobPipeline.jsx           # 0-Day discovery feed & Kanban CRM
        │   ├── KnowledgeVault.jsx        # Searchable self-learning QA manager
        │   ├── ProfileSettings.jsx       # Profile & recruiter preferences
        │   ├── BotConsole.jsx            # Live auto-apply worker controller
        │   ├── OutreachHub.jsx           # Multi-channel outreach tracker
        │   ├── EmailTracker.jsx          # Email sync & interview prep hub
        │   └── Settings.jsx              # Rate limits, auth manager & config
        └── services/
            ├── api.js
            └── websocket.js
```

---

## 6. Verification & Testing Protocol

```bash
# 1. Run Complete Automated Test Suite (FastAPI, Core, Adapters, HITL, Outreach, Email)
pytest backend/tests/ -v

# 2. Run Local Mock ATS Fixture Server & Form Filling Tests
python backend/tests/fixtures/mock_ats_server.py &
pytest backend/tests/test_adapters.py -v

# 3. Verify Turnkey One-Click Launch
./start.sh
```
