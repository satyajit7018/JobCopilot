# JobCopilot frontend

The JobCopilot UI: React + Vite + TypeScript + Tailwind, talking to the FastAPI backend under `/api`. In production `docker-compose.production.yml` builds this folder's `Dockerfile`; in development Vite serves it and proxies `/api` to the backend.

## Run it

```bash
# terminal 1: backend on :8000 (from repo root)
cd backend && uvicorn app.main:app --port 8000

# terminal 2: this app on :5173, proxying /api and /ws to :8000
cd frontend && npm install && npm run dev
```

Set `JOBCOPILOT_API` to proxy to a different backend. On a non-production backend the sign-in screen offers a passwordless development login.

| Script | What it does |
| --- | --- |
| `npm run dev` | Dev server with hot reload |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest unit tests |
| `npm run build` | Typecheck, then production build to `dist/` |
| `npm run preview` | Serve `dist/` with the production security headers |

## End-to-end tests

`e2e/` is a Playwright suite that boots a throwaway backend (SQLite, scratch data directory), builds this app and serves it with `vite preview` under the production CSP, then drives the real flows: sign-in and sign-out, first-run setup, jobs and the review page, applications, and axe accessibility checks (fails on serious or critical WCAG 2.1 AA issues). It never starts a real application run.

```bash
cd e2e && npm ci && npx playwright install chromium && npx playwright test
```

Set `JOBCOPILOT_E2E_PYTHON` if the backend's Python isn't `backend/venv/bin/python` or `python3`.

## Design rules

- **Tokens live only in `src/index.css`.** Tailwind's default palette and type scale are reset, so only the system values exist: `bg-surface`, `text-ink-2`, `border-line`, `bg-accent`, status colors `ok`/`warn`/`info`/`danger`, and six text sizes (`text-xs` 12 to `text-2xl` 32).
- **One accent color** (indigo) for primary actions and selection. Status colors are used for status only.
- **Build screens from `src/components/ui.tsx`** (Button, Badge, Card, Field, Alert, EmptyState, Spinner). Add a component there rather than styling one-offs in a page.
- **One primary button per screen.**
- **Plain language.** Navigation is Home, Jobs, Applications, Prep, Profile. Settings and Admin live in the account menu.

## Structure

```
src/
  lib/api.ts         fetch wrapper: bearer token, single-flight refresh on 401, readable errors
  lib/auth.tsx       AuthProvider: login, register, Google, MFA challenge, logout
  lib/jobs.ts        Job types mirroring backend models, status labels, score helpers
  lib/profile.ts     Profile, resume upload, recruiter answers, job-source preference
  lib/apply.ts       Tailoring, submission consent, apply task polling, held questions
  lib/application.ts One application: apply record, emails, status, follow-up, offer tools, timeline
  lib/prep.ts        Company brief, practice questions and scored feedback, questions to ask
  lib/settings.ts    Plan and billing, two-step sign-in, devices, security activity, export and delete
  lib/admin.ts       Platform numbers, users and roles, admin audit trail
  components/        AppShell (sidebar, mobile tab bar, account menu), core UI, profile forms
  pages/             one file per route
```

Sessions use the same `localStorage` keys as the previous UI did, so people who were signed in stay signed in after the switch. The job-source choice also keeps its old key (`jobcopilot_connected_portals`); it filters which new matches are shown and is not sent to the backend.

## Rebuild phases

1. **Foundation (done):** tokens, app shell, sign-in (password, Google, MFA), Home "Today", Jobs list, Applications board
2. **Setup and Profile (done):** three-step first run (resume, preferences, job sources, then a real search), Profile with resume summary/replace, contact details, preferences and job sources
3. **Review & apply (done):** per-job review page (match reasons, tailored materials, the details we'll fill in), practice run by default, real submission only with a recorded opt-in plus a per-application confirmation, live progress, and paused questions answered from Applications. Not yet possible without backend changes: previewing or downloading the tailored resume (the tailor endpoint returns neither the tailored content nor a downloadable file)
4. **Application detail (done):** timeline built from the job, its apply record and linked emails; readable recruiter emails with scheduling links; manual status changes; follow-up drafts once applied; offer check against the built-in salary ranges and a counter-offer draft. Drafts are copied, never sent
5. **Prep, Settings, Admin, and production (done):** interview prep with scored practice answers; settings for plan, submission consent, two-step sign-in (QR setup, backup codes), devices, security activity, data export and account deletion; admin metrics, users and role changes with confirmation. The previous vanilla-JS UI was removed and this app replaced it in `frontend/`.

## Production

`Dockerfile` builds the app with Node 22 and serves `dist/` from nginx (`nginx.conf`): hashed assets are cached for a year, `index.html` and `sw.js` are never cached, and `/api` and `/ws` proxy to the `api` service. CI builds the image on every PR.

Security headers live in `security-headers.conf`, included in every nginx location and also applied by `vite preview`; `backend/tests/test_security_headers_web.py` checks its `script-src` matches the API's.

`public/sw.js` replaces the previous UI's service worker with one that clears its caches and unregisters itself, so returning users aren't stuck on the old app.

**Features of the previous UI not rebuilt yet:** admin impersonation, organizations, the analytics funnel, the knowledge vault editor, referral and recruiter outreach drafts, pasting in recruiter emails by hand, the command palette, and installing as an app (PWA). The previous UI is in git history before the commit that removed it.
