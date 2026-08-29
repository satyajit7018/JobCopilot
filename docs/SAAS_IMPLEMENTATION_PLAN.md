# JobCopilot: Multi-Tenant Public SaaS Architecture & Implementation Plan

## Goal
Transform JobCopilot from a verified, fully-tested local-first autonomous job hunting OS into a **publicly deployable, multi-tenant SaaS platform** serving thousands of concurrent job seekers.

**Current State**: 8 milestones complete. 44/44 tests passing. 1,320/1,320 stress test assertions passing. Server running on `localhost:8000`.

---

## What Changes (and What Stays the Same)

> [!NOTE]
> All the core engine logic (resume parsing, SimHash deduplication, stealth browser automation, cover letter generation, email radar, interview studio, ESOP modeler) remains **100% unchanged**. The SaaS migration only wraps the existing engine with multi-user identity, cloud storage, and a distributed task queue.

---

## Phase 1 — Multi-Tenant Auth & Cloud Database (~1–2 weeks)

### 1.1 Add `user_id` to Every Database Table

#### [MODIFY] `backend/app/core/database.py`
- Add `user_id TEXT NOT NULL DEFAULT 'default'` column to every table (`profiles`, `vault`, `jobs`, `emails`, `outreach_records`, `hitl_events`).
- All `GET` queries gain a `WHERE user_id = ?` filter.
- All `INSERT` statements bind the caller's `user_id`.

#### [NEW] `backend/app/core/db_adapter.py`
- Unified `DatabaseAdapter` interface supporting both local **SQLite** and cloud **PostgreSQL**.
- Mode selected via `DB_MODE=sqlite|postgres` environment variable.
- Enables self-hosted users to continue running SQLite; cloud deployments use PostgreSQL with Row-Level Security.

---

### 1.2 JWT Authentication & OAuth2 Login

#### [NEW] `backend/app/api/auth.py`
- `POST /auth/register` — Email + Argon2id password signup.
- `POST /auth/login` — Returns a signed JWT `access_token` (15-min) and `refresh_token` (7-day, stored in `HttpOnly` Secure cookie).
- `GET /auth/oauth/google` — Google OAuth2 callback.
- `GET /auth/oauth/github` — GitHub OAuth2 callback.
- `POST /auth/refresh` — Rotates the refresh token silently.
- `POST /auth/logout` — Revokes the refresh token.

#### [MODIFY] `backend/app/api/endpoints.py`
- All existing API routes gain a `current_user = Depends(get_current_user)` FastAPI dependency.
- Every DB call passes `user_id=current_user.user_id`.

#### [NEW] `backend/requirements.txt` additions
```
python-jose[cryptography]>=3.3.0   # JWT signing
authlib>=1.3.0                     # OAuth2 client
asyncpg>=0.29.0                    # PostgreSQL async driver
alembic>=1.13.0                    # DB migrations
```

---

### 1.3 Database Migrations
#### [NEW] `backend/alembic/`
- Auto-generate migration scripts from the schema changes above.
- Migration `0001_add_user_id.py`: `ALTER TABLE ... ADD COLUMN user_id TEXT`.
- Migration `0002_add_indexes.py`: Composite indexes on `(user_id, status)`, `(user_id, priority_score DESC)`.

**Acceptance Criteria for Phase 1:**
```
✅ User A registers, uploads resume, runs 5 auto-applies
✅ User B registers independently — sees zero overlap with User A's data
✅ JWT refresh rotation works correctly on token expiry
✅ pytest backend/tests/test_auth.py -v → all pass
```

---

## Phase 2 — Distributed Worker Queue & Cloud Object Storage (~2–3 weeks)

### 2.1 Celery + Redis Async Task Queue

#### [NEW] `backend/app/tasks/celery_app.py`
- Celery application connected to Redis broker.
- Three priority queues:
  - `priority.high` — Live HITL resolution, dry-run previews
  - `priority.normal` — Scheduled auto-apply batch submissions
  - `priority.low` — Background discovery, email sync

#### [NEW] `backend/app/tasks/apply_task.py`
```python
@celery_app.task(bind=True, max_retries=3, queue='priority.normal')
def run_apply_job(self, user_id: str, job_id: str, submission_mode: str):
    """Runs the full Playwright stealth apply pipeline for one job."""
    # Existing BotRunner.apply_to_job() logic unchanged
```

#### [MODIFY] `backend/app/api/endpoints.py`
- `POST /api/bot/start` now enqueues `run_apply_job.delay(user_id, job_id)` instead of running synchronously.
- Response immediately returns `{"task_id": "...", "status": "QUEUED"}`.

#### [NEW] `backend/requirements.txt` additions
```
celery[redis]>=5.3.0
redis>=5.0.0
```

---

### 2.2 Cloud Object Storage for Resumes & Screenshots

#### [NEW] `backend/app/core/object_storage.py`
- `upload_resume(user_id, filename, content) → str` — Returns pre-signed S3/R2 URL.
- `upload_screenshot(user_id, job_id, png_bytes) → str` — Archives confirmation screenshots.
- `get_resume_url(user_id, filename) → str` — 15-minute expiring download link.
- Configured via `STORAGE_BACKEND=local|s3|r2` environment variable.
  - `local`: continues using `~/.jobcopilot/resumes/` (self-hosted).
  - `s3`: AWS S3 via `aioboto3`.
  - `r2`: Cloudflare R2 (S3-compatible API, zero egress fees).

#### [NEW] `backend/requirements.txt` additions
```
aioboto3>=12.0.0                   # Async S3/R2 client
```

---

### 2.3 Residential Proxy Rotation for Browser Workers

#### [MODIFY] `backend/app/bot/humanizer.py`
- Add `ProxyRotator` class supporting:
  - Direct (no proxy) for local/self-hosted mode.
  - Rotating residential proxies via Bright Data / Oxylabs API when `PROXY_PROVIDER=brightdata` env var is set.
- Each Playwright `BrowserContext` launches with a fresh proxy IP per job submission.

---

### 2.4 Distributed WebSocket via Redis Pub/Sub

#### [MODIFY] `backend/app/main.py` / `backend/app/api/ws_gateway.py`
- Replace single-node in-memory WebSocket manager with **Redis Pub/Sub channel per `user_id`**.
- Any API node can publish live bot screenshots, log lines, and HITL prompts — subscribed frontend receives them regardless of which server they hit.

**Acceptance Criteria for Phase 2:**
```
✅ Submit 10 auto-apply jobs simultaneously — all run in parallel Celery workers
✅ Resume uploaded and retrieved via pre-signed S3 URL
✅ Browser worker successfully routes through residential proxy (verified via IP check)
✅ WebSocket real-time telemetry works behind 2-node load balancer
✅ pytest backend/tests/test_workers.py -v → all pass
```

---

## Phase 3 — Production Deployment (~1 week)

### 3.1 Cloud Infrastructure Stack

| Component | Recommended Service | Why |
|:---|:---|:---|
| **API Cluster** | **Fly.io** (2–4 VM nodes) | Closest to free tier, auto-HTTPS, sub-100ms global routing |
| **Database** | **Supabase** (PostgreSQL + RLS) | Managed Postgres, built-in auth helpers, Row-Level Security |
| **Redis** | **Upstash Redis** | Serverless Redis, pay-per-use, zero cold-start |
| **Object Storage** | **Cloudflare R2** | Zero egress fees, S3-compatible API |
| **Browser Workers** | **Railway.app** or **Render.com** | Ephemeral Docker pods auto-scaled via Celery queue depth |
| **Proxies** | **Bright Data Residential** | 72M+ residential IPs, pay-per-GB |
| **CDN + WAF** | **Cloudflare** | Free WAF, DDoS protection, edge cache |

---

### 3.2 Environment Configuration

#### [NEW] `backend/.env.production`
```bash
# Database
DB_MODE=postgres
DATABASE_URL=postgresql://user:pass@db.supabase.co/jobcopilot

# Auth
JWT_SECRET=<256-bit-random-secret>
JWT_ALGORITHM=HS256
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...

# Redis (Celery Broker + Pub/Sub)
REDIS_URL=rediss://default:pass@upstash.io:6380

# Object Storage
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=...
R2_ACCESS_KEY=...
R2_SECRET_KEY=...
R2_BUCKET=jobcopilot-resumes

# Proxy
PROXY_PROVIDER=brightdata
BRIGHTDATA_CUSTOMER=...
BRIGHTDATA_ZONE=...
BRIGHTDATA_PASS=...

# App
JOBCOPILOT_DATA_DIR=/data
CORS_ORIGINS=https://jobcopilot.app,https://www.jobcopilot.app
```

---

### 3.3 Docker Compose (Updated for SaaS)

#### [MODIFY] `docker-compose.yml`
```yaml
services:
  api:
    build: ./backend
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4
    env_file: ./backend/.env.production
    depends_on: [redis]

  celery_worker:
    build: ./backend
    command: celery -A app.tasks.celery_app worker --loglevel=info -Q priority.high,priority.normal,priority.low
    env_file: ./backend/.env.production
    depends_on: [redis]
    deploy:
      replicas: 3        # Scale this up as user count grows

  redis:
    image: redis:7-alpine
    volumes: [redis_data:/data]

  frontend:
    build: ./frontend
    ports: ["3000:80"]
```

---

### 3.4 Monetization & Rate Limiting

#### [NEW] `backend/app/core/rate_limiter.py`
```
Free  Tier:  5 auto-applies/day,  basic discovery
Pro   Tier:  30 auto-applies/day, 0-day feeds, outreach ($29/mo)
Elite Tier:  Unlimited,           residential proxies, priority queue ($79/mo)
```

**Acceptance Criteria for Phase 3:**
```
✅ 100 concurrent users simulated via Locust load test with <500ms P95 API latency
✅ Celery worker fleet auto-scales from 1→10 pods when queue depth > 50 tasks
✅ Cloudflare WAF blocks DDoS attempt during load test
✅ Zero data cross-contamination across 100 test user accounts
✅ Full disaster recovery tested: backup exported, DB wiped, restored in < 60s
```

---

## Full Implementation Timeline

```
Week 1–2:   Phase 1 (Auth + Multi-Tenant DB)
Week 3–5:   Phase 2 (Celery Queue + S3 + Redis Pub/Sub)
Week 6:     Phase 3 (Production Deploy + Monitoring + Billing)
Week 7:     Load Testing, Security Audit, Beta Launch
```
