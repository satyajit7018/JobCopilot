# 4. API Versioning and Evolutionary Deprecation Policy

Date: 2026-09-06

## Status

Accepted

## Context

As JobCopilot transitions from a single-tenant web UI to supporting mobile PWA clients, desktop companions, third-party integrations, and automated headless consumers, unversioned breaking changes in HTTP endpoints could disrupt running clients.

A formal versioning schema and transparent deprecation lifecycle are required before publishing public APIs and OpenAPI specifications.

## Decision

We instituted a **Semantic Prefix Versioning and RFC 8594 Deprecation Lifecycle**:
1. **Canonical Versioning**:
   - All modern endpoints are mounted under the canonical prefix `/api/v1/` (e.g., `/api/v1/jobs`, `/api/v1/auth`, `/api/v1/analytics`).
   - OpenAPI specifications and client bindings are generated from `/api/v1/openapi.json`.
2. **Backward Compatibility Alias**:
   - The unversioned prefix `/api/` remains operational as a backward-compatible alias to avoid breaking legacy clients and test suites.
3. **Deprecation Signals (RFC 8594)**:
   - Requests invoking unversioned `/api/*` endpoints receive standard HTTP deprecation headers:
     - `Deprecation: @1788500000` (Unix timestamp or true boolean indicator).
     - `Sunset: Sat, 06 Mar 2027 00:00:00 GMT` (Minimum 6-month graceful migration window).
     - `Link: </api/v1/...>; rel="successor-version"`.
4. **Breaking Changes**:
   - Breaking field deletions or schema alterations require a new major version prefix (`/api/v2/`).
   - Minor additive changes (new optional fields, new query parameters) do not trigger version bumps.

## Consequences

### Positive
- Client developers and automated SDKs have predictable stability guarantees.
- Sunset dates and successor versions are communicated programmatically in every HTTP response.

### Negative / Trade-offs
- Router aggregation must wire dual mounts (canonical `/api/v1` and compatibility `/api` with middleware).
