# System Architecture

## Overview

```
                     ┌─────────────────────────────┐
                     │   Parent Platform (Module 1) │
                     │   issues JWTs on login        │
                     └───────────────┬──────────────┘
                                     │ Bearer JWT
                                     ▼
┌────────────────────────────────────────────────────────────────┐
│  AI Workflow Simulation Engine (this repo)                     │
│                                                                  │
│  ┌────────────┐   ┌──────────────┐   ┌────────────────────┐    │
│  │  FastAPI   │──▶│  Services    │──▶│  SQLAlchemy Models  │    │
│  │  Routes    │   │  (generators,│   │  (14 tables)         │    │
│  │  (JWT-     │   │  sprint      │   └──────────┬───────────┘    │
│  │  gated)    │   │  engine,     │              │                │
│  └────────────┘   │  AIService)  │              ▼                │
│                    └──────────────┘   ┌─────────────────────┐    │
│                                        │  PostgreSQL          │    │
│                                        └─────────────────────┘    │
└────────────────────────────────────────────────────────────────┘
```

## Layers

- **`app/api/routes/*`** — FastAPI routers. Every route depends on
  `get_current_user` (JWT validation) and an ownership-check dependency
  (`get_owned_company` / `_get_owned_project` / `_get_owned_task`) so a
  student can only ever read or mutate their own simulation.
- **`app/services/*`** — business logic, framework-agnostic:
  - `company_generator.py` (Feature 1)
  - `project_generator.py` (Feature 2)
  - `sprint_engine.py` (Feature 3)
  - `ai_service.py` — the `AIService` abstract interface plus
    `MockAIService` (active today) and `GeminiAIService` (activates the
    moment `GEMINI_API_KEY` is set in the environment — no code changes).
- **`app/models/*`** — SQLAlchemy 2.0 declarative models, one file per
  table family, all registered on a shared `Base` via `app/models/__init__.py`
  so Alembic autogenerate sees the full schema.
- **`app/schemas/*`** — Pydantic request/response contracts, decoupled from
  the ORM models (`from_attributes=True` for reads).
- **`app/core/*`** — cross-cutting concerns: `config.py` (env-driven
  settings), `database.py` (engine/session), `security.py` (JWT
  validation — this service never issues tokens, only validates them).

## Why an AIService abstraction

Feature 6 (AI Project Manager) and Feature 7 (AI Teammates) call
`ai_service.generate_text(...)` exactly like the Company Generator did in
Phase 1. Building and testing the Mock provider first — and later
extending it with context-aware chat replies (see
`MockAIService.generate_text`'s manager/teammate branches) — means the
whole system, chat included, is fully runnable with zero API keys. Set
`GEMINI_API_KEY` to switch every one of these call sites to real Gemini,
with no code changes anywhere.

## Multi-tenancy model

Each `Company` row is scoped to one `student_id` (taken from the JWT
subject claim, not from user input on protected paths — the `POST
/api/generate` endpoint explicitly checks `payload.student_id ==
user.student_id` and rejects mismatches with 403). All ownership
dependencies walk the FK chain (`Task → Sprint → Project → Company`) to
confirm the requester owns the resource before returning or mutating it.
The WebSocket endpoint applies the same check before accepting the
connection.

## The stateful workflow engine (Feature 8) and dynamic events (Feature 9)

`ProjectState` (one row per project) is the single source of truth:
`completed_tasks`, `pending_tasks`, `missed_deadlines`, `bug_count`,
`stress_level`, `manager_satisfaction`, `team_satisfaction`, etc. Two
things read and write it:

- **`app/services/workflow_engine.py`** — called from the task-status
  route on every completion, and from a dedicated bug-report route. It
  never invents random outcomes; it reads the current numbers and applies
  fixed rules (missed deadline → satisfaction down, stress up, and an
  emergency-meeting event once 3 deadlines are missed; bug reported →
  bug_count up, and an emergency-meeting event every 3rd bug; sprint
  finished early → satisfaction up + a client bonus-feature event).
- **`app/services/events_engine.py`** — the single `trigger_event(...)`
  entry point every rule (and a manual demo/instructor endpoint) calls.
  One call creates the `Event` row, a `Notification`, an `ActivityLog`
  entry, and a live WebSocket push — so nothing can fire an event without
  it being visible in all three places at once.

A real APScheduler job (`app/services/scheduler_jobs.py`) runs every 60s
and checks every project's `stress_level`, pushing a manager check-in
notification once it crosses 80/100 — the one genuinely time-driven
(rather than action-driven) piece of the system, and still gated on real
state rather than firing unconditionally.

## Real-time layer (Feature 17)

`app/websockets/manager.py` is an in-memory `ConnectionManager` keyed by
`company_id`. Chat sends, task status changes, bug reports, and events
all call `ws_manager.broadcast(company_id, event_type, data)` after
committing to the database, so any open tab for that company gets the
update within about a second — confirmed with a real WebSocket test
client during development (see `docs/VERIFICATION.md`).

This is single-process by design for now: correct for the one backend
container in `docker-compose.yml`, but a multi-instance deployment would
need Redis pub/sub (or similar) so a broadcast reaches clients connected
to a different replica than the one that handled the write.
