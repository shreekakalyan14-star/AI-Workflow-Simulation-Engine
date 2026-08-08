# AI Workflow Simulation Engine

Simulates a real software company internship. Given `(student_id, role,
technology_stack, difficulty, company_type)`, it generates a company, a
manager, a project, 4 sprints, and every task (with real priorities,
estimates, deadlines, acceptance criteria, and dependencies) — then drives
task/Kanban state through a persistent PostgreSQL-backed workflow.

## Current status: Phase 3 of 3 — complete

This repo was built in phases so each one is fully real and tested before
the next started, rather than 20 features half-done at once.

| Phase | Scope | Status |
|---|---|---|
| **1** | DB schema (all 14 tables) · Company Generator · Project Generator · Sprint Engine · Kanban board · Task lifecycle · REST APIs · JWT validation · Alembic · Docker · Tests | **Done** |
| **2** | Frontend: React 19 + Vite + Tailwind v4 Kanban board (drag-and-drop) + dashboard + charts + animations, wired end-to-end to Phase 1's real API | **Done** |
| **3** | AI Project Manager + AI Teammates chat, WebSockets, Dynamic Events Engine, Stateful Workflow rules, Meetings, Notifications, Activity Log, Timeline, APScheduler background job | **Done — see below** |

Nothing here is a placeholder — every endpoint and every frontend flow in
every phase was exercised end-to-end against a real PostgreSQL database
(and, for Phase 3, a real WebSocket client) while building it. See
`docs/VERIFICATION.md` for the full log, including the exact requests run
and their responses.

## What's implemented right now

- **Full schema**: `companies, managers, projects, sprints, tasks,
  task_dependencies, team_members, messages, notifications, events,
  activity_logs, project_states, meeting_schedules, sprint_reviews` — all
  with UUID PKs, FKs, indexes, and `created_at`/`updated_at`.
- **Feature 1 — AI Company Generator**: realistic name/industry/mission/
  description per company type (startup, product company, MNC, healthcare,
  banking, e-commerce, education), plus a Manager with a personality.
- **Feature 2 — Project Generator**: role/stack/difficulty-aware project
  title, objectives, modules, deliverables, duration.
- **Feature 3 — Sprint Engine**: splits the project into 4 sprints,
  distributes modules, generates tasks with priority/hours/deadline/
  description/acceptance criteria, and real intra-sprint dependencies.
- **Feature 4 — Kanban board**: `GET /api/projects/{id}/board`, tasks
  grouped by status column.
- **Feature 5 — Task management**: `PATCH /api/tasks/{id}/status` drives
  start/pause/complete/block, enforces dependency ordering (can't start a
  task whose dependency isn't done), and syncs `project_states` live.
- **AIService abstraction**: `MockAIService` (deterministic, zero external
  calls, used today) and `GeminiAIService` (activates automatically the
  moment `GEMINI_API_KEY` is set) — this is what Phase 3's AI Manager and AI
  Teammates will build on.
- JWT validation (validate-only — this service never issues tokens; it
  trusts tokens issued by the parent platform / Module 1), multi-tenant
  isolation (a student can only see their own company/project/tasks),
  Swagger docs, CORS, Alembic migrations, Docker, and a real pytest suite.
- A dev-only `POST /api/dev/token` endpoint (hard-disabled unless
  `ENVIRONMENT=development`) so this service — and its frontend — are
  testable standalone before Module 1 issues real tokens.

### Phase 2 — Frontend

- **Design**: a deliberate "engineering workbench" identity — deep-navy
  (not pure black) surfaces, Space Grotesk/Inter/JetBrains Mono type
  system, and a signature terminal-style status strip
  (`aiwse@sim:~/company/project (sprint 2/4) ▍ manager: satisfied`) that
  doubles as the live manager-mood indicator.
- **Onboarding** (`/`): dev sign-in + the generation form (role, tech
  stack, difficulty, company type) → calls the real `POST /api/generate`.
- **Dashboard** (`/dashboard`): company/project/manager summary,
  objectives, and three live Recharts visualizations — completion donut,
  task-distribution bar chart (colored by the same status hues as the
  board), and sprint progress.
- **Kanban board** (`/board`): all 6 status columns
  (Backlog/To Do/In Progress/Review/Blocked/Completed), drag-and-drop via
  `@dnd-kit` that calls the real `PATCH /api/tasks/{id}/status`, a slide-over
  task detail drawer (acceptance criteria, dependencies with live
  completion state, Start/Pause/Send-to-review/Mark-complete/Mark-blocked
  actions, deliverable link field).
- Framer Motion throughout: animated boot-sequence loading screen, page
  transitions, card enter/exit, drawer slide-in.
- React Query for all data fetching/mutation + cache invalidation; axios
  client with bearer-token injection.

### Phase 3 — AI chat, dynamic events, meetings, real-time

- **Feature 6 — AI Project Manager**: in-character replies grounded in the
  live `ProjectState` (mentions real missed-deadline/completion numbers),
  voiced per personality (strict/friendly/corporate/startup founder). Works
  today with zero API key via an upgraded `MockAIService`; set
  `GEMINI_API_KEY` to switch to real Gemini with no code changes.
- **Feature 7 — AI Teammates**: 3 generated per company at simulation
  creation (name/role/personality/skill level), with persistent, in-character
  chat.
- **Feature 8 — Stateful Workflow Engine**: task completion, missed
  deadlines, and bug reports all mutate the real `ProjectState` and can
  cascade into real events — e.g. 3 missed deadlines → emergency meeting
  event; every 3rd bug reported → emergency meeting event; early sprint
  completion → positive manager feedback + a client bonus-feature event.
  Nothing here is random — every rule reads real state before acting.
- **Feature 9 — Dynamic Events Engine**: a single `trigger_event(...)`
  entry point creates the Event row, a Notification, an ActivityLog entry,
  and a live WebSocket push, in one call. Reachable both automatically
  (via the workflow engine) and manually (`POST
  /api/projects/{id}/events/trigger`, useful for demos/instructor tooling).
- **Feature 10 — Meetings**: Sprint Planning + Sprint Review auto-scheduled
  for every one of the 4 sprints at generation time (8 meetings total),
  with a real agenda and participant list; students can mark them
  completed with notes/attendance/action items.
- **Feature 11 — Timeline**: one endpoint aggregates completed tasks,
  events, meetings, and chat messages into a single chronological feed —
  confirmed sorted correctly.
- **Feature 12 — Notifications** & **Feature 13 — Activity Log**: created
  automatically by chat, bug reports, workflow-engine rule firings, and
  meeting completions; surfaced in the frontend via a notifications bell
  (unread count + mark-as-read) and the timeline feed.
- **Feature 17 — WebSockets**: a real `ConnectionManager`
  (`/ws/companies/{id}?token=...`) broadcasts chat messages, task updates,
  bug reports, and events live to any open tab — confirmed with an actual
  WebSocket client receiving a push within ~1 second of a task status
  change.
- **APScheduler**: a real background job runs every 60s, checks every
  project's live `stress_level`, and pushes a manager check-in
  notification once it crosses 80/100 — driven by state, not a timer
  alone.
- **Frontend**: a Chat page (manager + 3 teammate threads, real-time via
  the WebSocket hook), a Timeline page (chronological feed + a pending-
  meetings panel with a complete-meeting action), and a notifications
  bell wired into the header.

### Known simplifications (documented, not hidden)

- The `messages` table is one stream per company, not one thread per
  conversation partner — a student message doesn't record which teammate
  it was aimed at. The team chat history endpoint returns all
  student+teammate messages for the company rather than a strictly
  scoped single-teammate thread. A `recipient_id` column on `Message`
  would be the natural follow-up.
- The WebSocket connection manager is in-memory and single-process —
  correct for one backend instance (as run here and in `docker-compose.yml`),
  but a multi-instance deployment would need Redis pub/sub or similar so
  broadcasts reach clients connected to a different replica.
- "Documentation missing" nudges (mentioned in the original spec's Feature
  8 examples) were not implemented as a distinct rule — the shipped rules
  (missed deadlines, bug thresholds, early completion) are the ones with
  clear, testable state triggers.

## Quick start (Docker — recommended)

```bash
cd docker
docker compose up --build
```

- Frontend: http://localhost:5173
- API: http://localhost:8000
- Swagger docs: http://localhost:8000/docs
- Postgres: localhost:5432 (user `aiwse` / password `aiwse_password` / db `aiwse_db`)

Migrations run automatically on container start. Open the frontend, enter
any student ID to sign in (dev-only token mint — see below), fill out the
generation form, and you're in a live simulation.

## Quick start (local, no Docker)

Backend:
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # edit DATABASE_URL to point at your local Postgres
alembic upgrade head
uvicorn app.main:app --reload
```

Frontend (separate terminal):
```bash
cd frontend
npm install
cp .env.example .env   # points at http://localhost:8000 by default
npm run dev
```
Open http://localhost:5173.

## Try it

Every endpoint requires a bearer JWT signed with `JWT_SECRET_KEY` (shared
secret with whatever issues tokens — Module 1 in the full platform). For
local testing, mint one yourself:

```python
from jose import jwt
token = jwt.encode(
    {"sub": "student_001", "student_id": "student_001", "role": "student"},
    "change-me-to-the-shared-signing-secret",
    algorithm="HS256",
)
```

```bash
curl -X POST http://localhost:8000/api/generate \
  -H "Authorization: Bearer <token>" -H "Content-Type: application/json" \
  -d '{
    "student_id": "student_001",
    "role": "Backend Developer",
    "technology_stack": ["Python", "FastAPI", "PostgreSQL"],
    "difficulty": "intermediate",
    "company_type": "startup"
  }'
```

## Running tests

Tests run against a **real** Postgres database (no mocking of the DB layer).

```bash
# with docker: db already running from `docker compose up`
createdb -h localhost -U aiwse aiwse_test_db   # once
cd backend && pip install -r requirements.txt
cd .. && pytest -v
```

## Docs

- `docs/ARCHITECTURE.md` — system architecture
- `docs/DATABASE_SCHEMA.md` — full schema reference
- `docs/API.md` — API reference (Swagger is the source of truth at `/docs`)
- `docs/INSTALLATION.md` — installation guide
- `docs/DEPLOYMENT.md` — deployment guide
- `docs/INTEGRATION.md` — how Module 1 (auth) and Module 3 (whatever consumes
  this) plug in
- `docs/VERIFICATION.md` — what was actually run and tested while building this
