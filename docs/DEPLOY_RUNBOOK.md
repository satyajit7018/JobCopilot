# JobCopilot Deploy Runbook

Two supported targets: **Docker Compose** (single prod-like host) and
**Kubernetes** (`infra/k8s/`). Both run on **PostgreSQL** in production —
SQLite is dev/test only.

---

## A. Docker Compose (single host)

### 1. Prerequisites
- Docker Engine + Compose v2 on the host.
- A filled-in `.env.production` (copy from `.env.production.example`).
  Generate secrets:
  ```bash
  openssl rand -base64 48   # JWT_SECRET
  openssl rand -base64 32   # JOBCOPILOT_MASTER_KEY
  openssl rand -base64 24   # POSTGRES_PASSWORD
  ```

### 2. Bring up the stack
```bash
docker compose --env-file .env.production -f docker-compose.production.yml up -d --build
```
Startup order is enforced by healthchecks: Postgres and Redis become
healthy first, then the API boots (the Postgres adapter creates its tables
on first connection via `CREATE TABLE IF NOT EXISTS`), then the worker and
frontend start.

### 3. Smoke check
```bash
curl -fsS http://localhost:8000/health          # -> 200, status ok
docker compose -f docker-compose.production.yml ps   # all services healthy/running
docker compose -f docker-compose.production.yml exec postgres \
  psql -U jobcopilot -d jobcopilot -c '\dt'      # tables exist (users, profiles, jobs, ...)
```
The API refuses to boot in production without `JWT_SECRET` (>=32 chars) and
`JOBCOPILOT_MASTER_KEY` — this is the fail-closed guard in `settings.py`.

### 4. Validate the compose file before deploying (no daemon needed)
```bash
docker compose -f docker-compose.production.yml config >/dev/null && echo OK
```

---

## B. Kubernetes (`infra/k8s/`)

### 1. Secrets & config
`infra/k8s/secrets.yaml` is a **template** — every value is a `REPLACE_...`
placeholder. Do **not** commit real secrets. Inject them via a sealed-secrets
/ SSM / Vault flow (P1-3), or for a manual apply, create the Secret out of band:
```bash
kubectl -n production create secret generic jobcopilot-secrets \
  --from-literal=JWT_SECRET=... \
  --from-literal=JOBCOPILOT_MASTER_KEY=... \
  --from-literal=DATABASE_URL='postgresql://...?sslmode=require' \
  --from-literal=REDIS_URL='rediss://...'
```
The `jobcopilot-config` ConfigMap already sets `ENV=production`,
`DB_MODE=postgres`, `STORAGE_BACKEND=s3`.

### 2. Build & push the image
```bash
docker build -t <registry>/jobcopilot/api:<tag> ./backend
docker push <registry>/jobcopilot/api:<tag>
# update image: in infra/k8s/api-deployment.yaml + worker-deployment.yaml
```

### 3. Dry-run, then apply
```bash
kubectl apply --dry-run=client -f infra/k8s/     # validate manifests
kubectl apply -f infra/k8s/
kubectl -n production rollout status deploy/jobcopilot-api
```
Liveness/readiness probes hit `/health` on :8000; the Deployment runs as a
non-root user with a read-only root filesystem.

### 4. Smoke check
```bash
kubectl -n production port-forward svc/jobcopilot-api 8000:8000 &
curl -fsS http://localhost:8000/health
```

---

## Notes / open items
- **Migrations:** the Postgres adapter self-bootstraps its schema at runtime.
  Reconciling that with the Alembic migrations in `backend/alembic/` (and a
  CI drift check) is tracked as **P1-2**.
- **Terraform** (`infra/terraform/`): run `terraform plan` against your
  backend before `apply`; not covered by an automated check yet.
- The Compose stack keeps `STORAGE_BACKEND=local`; the K8s stack uses S3.
