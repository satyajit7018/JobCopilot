# JobCopilot — Security & Quality Audit

_Whole-project audit: ~21k LOC backend Python, ~8.4k LOC frontend, plus infra/CI/docs._

This document records the findings of a full-codebase audit and tracks remediation.
Items fixed in the accompanying change are marked ✅; open items are marked ⬜.

## Critical

- ✅ **Hardcoded `JWT_SECRET` default, only guarded in production.**
  The default signing key was committed to source (`settings.py`), and the fail-closed
  guard only fired when `ENV=production`. Any dev/staging/misconfigured instance signed
  tokens with a world-readable key, allowing forgery of any user's JWT.
  **Fix:** `JWT_SECRET` now defaults to `None`. Auth resolves it fail-closed — a strong
  external secret is mandatory in production; in non-production, a cryptographically random
  **ephemeral per-process** secret is generated instead of a committed key
  (`app/api/auth.py::_resolve_jwt_secret`).

## Medium

- ✅ **Unpinned dependencies.** `backend/requirements.txt` used lower bounds (`>=`) only,
  giving non-reproducible builds and drifting `pip-audit` results.
  **Fix:** direct dependencies pinned to tested versions (`==`). Pinning surfaced known CVEs,
  which were then patched: `python-multipart` → 0.0.31, `requests` → 2.33.0. Test-only tools
  (`pytest`, `pytest-asyncio`) were removed from the runtime requirements (CI installs them
  separately). These patched releases require Python ≥3.10, so `requires-python` was raised
  accordingly (3.9 is end-of-life).

- ✅ **`starlette` advisories PYSEC-2026-161/248/249/2280/2281 fixed by upgrade.**
  All fixes are in `starlette` 1.x. `fastapi` 0.128.8 capped `starlette<1.0.0`, but
  `fastapi` >=0.135.0 relaxed it to `starlette>=0.46.0`. Upgraded `fastapi` -> 0.141.1
  and pinned `starlette` -> 1.3.1, which clears all five advisories with **no `pip-audit`
  suppressions**. The upgrade crosses the `starlette` 1.0 major boundary; the codebase only
  touches stable surface (`BaseHTTPMiddleware`, `Request`/`Response`, `TestClient`,
  `WebSocketDisconnect`), and the full suite runs in CI on Python 3.11.
- ⬜ **JWTs stored in `localStorage`** (`frontend/js/app.js`) are readable by any XSS.
  Escaping is currently disciplined, but a refresh token should live in an httpOnly,
  `SameSite` cookie rather than `localStorage`.
- ⬜ **CI quality gates do not gate.** `gitleaks` uses `continue-on-error`, `semgrep`
  ends with `|| true`, and `ruff`/`mypy` run against only a handful of files.
  Make lint/type whole-repo and let SAST/secret scans fail the build.
- ⬜ **`deploy.yml` is a no-op.** The actual deploy steps (`kubectl apply`, rollback) are
  commented out. Either wire it up or remove it.

## Low

- ⬜ **Coverage padded to the gate.** Total is ~80.8% vs an 80% gate, cleared largely by
  `backend/tests/test_coverage_gate_boost.py`. Core modules are thin (llm_client ~60%,
  postgres_adapter ~69%, bot.runner ~65%). Replace the boost file with real tests on those paths.
- ⬜ **Idempotency trusts an unsigned `sub` claim** (`app/api/middleware.py`): it decodes the
  JWT with `verify_signature=False` to namespace idempotency keys. Use the already-verified
  `request.state.user_id`.
- ⬜ **~46 silent broad `except Exception` handlers** swallow errors (return `None`/`[]`/`{}`).
  Route through the existing `security_logger`/telemetry instead.
- ⬜ Stray dev scripts at the backend root (`stress_test_30*.py`, `test_phase1.py`) belong
  under `tests/`; 8 `print()` calls in app code should use logging.

## Verified good (no action needed)

- SQL access is fully parameterized (`%s`); the only f-string SQL is internal DDL on
  constant table names.
- Passwords use Argon2id (+ PBKDF2-600k legacy path) with constant-time comparison.
- JWT verification uses `hmac.compare_digest`, checks expiry + `jti` revocation, and ignores
  the header `alg` (immune to alg-confusion / `alg:none`).
- Credential vault uses an Argon2 KDF plus envelope encryption with key versioning.
- CORS default is localhost-only with no wildcard.
- Frontend consistently uses `escapeHTML()` and a `sanitizeUrl()` helper on external data.
