# Integration Guide

This service is designed to be dropped into the larger AI Internship
Simulator platform as an independent microservice, reachable only via its
REST API (and, in Phase 3, WebSockets).

## Integrating with Module 1 (Auth / Login)

This service **never issues JWTs** — it only validates them
(`app/core/security.py`). For integration:

1. Module 1 and this service must share the same `JWT_SECRET_KEY` and
   `JWT_ALGORITHM` (defaults to `HS256`).
2. Tokens issued by Module 1 must include a subject claim identifying the
   student — either `sub` or `student_id` — matching what this service
   expects in `get_current_user()`.
3. Optionally include a `role` claim if Module 1 wants to use this
   service's `require_role(...)` dependency for role-gated endpoints (not
   currently used on any Phase 1 route, but available).
4. On login, Module 1 should redirect (or the frontend should call)
   `POST /api/generate` with the student's chosen `role`,
   `technology_stack`, `difficulty`, and `company_type` to kick off their
   simulation — passing the Module-1-issued JWT as the bearer token.

No shared database access is required or assumed — this service owns its
own Postgres schema entirely.

## Integrating with Module 3 (or any downstream consumer)

Everything this service exposes is plain REST + JSON (Swagger/OpenAPI at
`/docs` and `/openapi.json`), so Module 3 can either:

- **Call the REST API directly** the same way the frontend does — every
  endpoint in `docs/API.md` is fully documented and stable within a major
  version.
- **Generate a typed client** from `/openapi.json` using `openapi-generator`
  or similar, for strongly-typed integration.

Recommended integration points for Module 3:

- `GET /api/projects/{id}/state` — poll or subscribe to this for
  higher-level orchestration decisions (e.g. unlocking new content when
  `completed_tasks` crosses a threshold).
- `POST /api/generate` — trigger a new simulation programmatically (e.g.
  from an admin/instructor panel) as long as you can mint a valid JWT for
  the target student.

## What's intentionally NOT shared

- No shared database connection — this service's Postgres instance is
  private to it. Any cross-module data needs must go through the REST API.
- No token issuance — this service is a pure JWT consumer.

## WebSockets (implemented)

`ws://.../ws/companies/{company_id}?token=<jwt>` pushes live updates
(chat messages, task status changes, bug reports, dynamic events) to any
connected client. The token is passed as a query parameter — browsers
can't set custom headers on the WS handshake — and validated identically
to REST bearer tokens, with the same company-ownership check. See
`docs/API.md` for the frame format.

The connection manager (`app/websockets/manager.py`) is in-memory and
single-process. If Module 3 (or any consumer) needs to receive these
pushes from a different process than the one handling writes, or if this
service is ever scaled to multiple replicas, that's the one piece that
would need Redis pub/sub (or similar) instead of the in-memory dict.
