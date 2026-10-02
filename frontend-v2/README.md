# JobCopilot frontend v2

The redesigned UI: React + Vite + TypeScript + Tailwind. It talks to the existing FastAPI backend under `/api` and needs no backend changes. The legacy UI in `../frontend/` keeps shipping until every screen here is rebuilt.

## Run it

```bash
# terminal 1: backend on :8000 (from repo root)
cd backend && uvicorn app.main:app --port 8000

# terminal 2: this app on :5173, proxying /api and /ws to :8000
cd frontend-v2 && npm install && npm run dev
```

Set `JOBCOPILOT_API` to proxy to a different backend. On a non-production backend the sign-in screen offers a passwordless development login.

| Script | What it does |
| --- | --- |
| `npm run dev` | Dev server with hot reload |
| `npm run typecheck` | `tsc --noEmit` |
| `npm test` | Vitest unit tests |
| `npm run build` | Typecheck, then production build to `dist/` |

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
  components/        AppShell (sidebar, mobile tab bar, account menu) and core UI
  pages/             one file per route
```

Sessions use the same `localStorage` keys as the legacy UI, so signing in to one signs you in to both.

## Rebuild phases

1. **Foundation (done):** tokens, app shell, sign-in (password, Google, MFA), Home "Today", Jobs list, Applications board
2. First-run setup flow and Profile (resume upload, preferences, connected sites)
3. Review & apply (tailored resume diff, cover letter, explicit approve)
4. Application detail (timeline, emails, offers)
5. Prep, Settings, Admin; then switch the Docker/nginx image to serve v2 and retire `../frontend/`
