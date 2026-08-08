# Verification Log

This isn't a claims doc — it's a record of what was actually executed
while building Phase 1, so you know exactly what's been proven to work
versus what's implemented-but-unexercised.

## Environment used

PostgreSQL 16 (installed via `apt-get install postgresql`), Python 3.12,
a virtualenv with `requirements.txt` installed, all inside the build
sandbox (no Docker daemon available there — the Dockerfile/compose file
were written to the same spec but validated via the equivalent local
Postgres + venv setup instead of `docker compose up` directly).

## What was run

1. **`alembic revision --autogenerate`** — correctly detected and generated
   all 14 tables and every index from the SQLAlchemy models, with zero
   manual edits needed.
2. **`alembic upgrade head`** — applied cleanly against a real Postgres 16
   instance.
3. **Schema confirmed** via `information_schema.tables` — all 14 tables
   present: `activity_logs, companies, events, managers,
   meeting_schedules, messages, notifications, project_states, projects,
   sprint_reviews, sprints, task_dependencies, tasks, team_members`.
4. **Live server** (`uvicorn app.main:app`) started successfully against
   the real database.
5. **`POST /api/generate`** called with a real signed JWT — returned a
   real company, project, 4 sprints, and 9 tasks, all persisted (verified
   by reading them back in subsequent requests, not just trusting the
   response body).
6. **Generated content sanity-checked**: company name "Orbitly Labs",
   mission/description text from `MockAIService`, manager "Aditi
   Whitfield" (startup_founder personality), project "Inventory
   Management System API" with real modules
   (`Third-Party Integrations, Reporting & Analytics, Testing & QA Suite,
   Real-Time Updates`) and deliverables.
7. **`GET /api/projects/{id}/state`** — confirmed a `ProjectState` row was
   created alongside the project with sane defaults.
8. **`GET /api/projects/{id}/board`** — confirmed all 9 generated tasks
   appear, all in `backlog`, grouped correctly.
9. **Dependency enforcement tested live**: attempting to move a dependent
   task to `in_progress` before its anchor task was `completed` returned
   `409` as designed; after completing the anchor, the dependent task
   moved to `in_progress` successfully; `project_states.completed_tasks`
   incremented to `1` as a direct result.
10. **Multi-tenant isolation tested live**: a second JWT for a different
    `student_id` got `403` when trying to read the first student's
    company; no token at all got `401`.
11. **Swagger/OpenAPI**: `/docs` and `/openapi.json` both returned `200`.
12. **Full pytest suite** (`tests/test_api.py`, 9 tests) — run against the
    real `aiwse_test_db` Postgres database, all passing. Covers: health
    check, full generation flow, student_id mismatch rejection,
    company/manager reads, project/state reads, Kanban board grouping and
    task-count consistency, dependency-blocked-then-unblocked task
    lifecycle with project-state sync, cross-tenant 403, missing-token 401.

## What was NOT run

- `docker compose up` itself was not executed (no Docker daemon in the
  build sandbox) — the Dockerfile and compose file follow the exact same
  install/migrate/run steps that were verified locally, but you should
  run `docker compose up --build` yourself as the final check before
  relying on it in CI/production.
- Real Gemini API calls — `GEMINI_API_KEY` was left empty throughout, so
  only `MockAIService` was exercised. `GeminiAIService`'s HTTP call shape
  follows Gemini's documented `generateContent` REST contract but has not
  been called against the live API.

## Phase 2 — Frontend verification

1. `npm run build` — production Vite build completed cleanly (1118
   modules transformed, no errors).
2. `npm run dev` — real dev server started and served `index.html`
   (`200 OK`).
3. **CORS preflight** — an `OPTIONS` request with `Origin:
   http://localhost:5173` against the backend returned
   `access-control-allow-origin: http://localhost:5173`, confirming the
   frontend and backend can actually talk cross-origin as configured.
4. **Full E2E flow exercised via the exact same requests the React app
   makes**: mint dev token → `POST /api/generate` (Frontend Developer /
   React+Vite+Tailwind / intermediate / ecommerce) → `GET
   /api/projects/{id}/board` → `PATCH /api/tasks/{id}/status`. Every
   response shape was checked field-by-field against what
   `Dashboard.jsx`, `Board.jsx`, `TaskCard.jsx`, and
   `TaskDetailDrawer.jsx` read (e.g. `depends_on_task_ids`,
   `manager_satisfaction`, `sprint.status` values of
   `planned/active/completed` matching the burndown chart's status
   checks) — no mismatches found.
5. What was **not** run: an actual browser (no headless browser available
   in the build sandbox), so drag-and-drop interaction, Framer Motion
   timing, and Recharts rendering were verified by code review and by
   confirming the underlying data contract is correct, not by visual
   screenshot. Run `npm run dev` yourself and open http://localhost:5173
   for the first visual check.

## Phase 3 — AI chat, dynamic events, meetings, real-time verification

1. **Generation** re-run end-to-end after adding team/meeting generation —
   confirmed 3 team members and 8 meetings (Sprint Planning + Sprint
   Review × 4 sprints) created alongside the company/project/sprints/tasks
   in the same atomic transaction.
2. **AI Manager chat** — `POST /api/companies/{id}/chat/manager` returned
   a real in-character reply referencing actual state ("Current velocity
   shows 0 tasks completed — on track overall" for a corporate-personality
   manager on a freshly generated project). History endpoint confirmed
   both messages persisted in order.
3. **AI Teammate chat** — `POST /api/companies/{id}/chat/team/{id}`
   returned a real in-character teammate reply.
4. **Bug report → workflow engine → events chain** — reported 3 bugs on a
   real project via the API; confirmed `bug_count` reached 3, a
   `bug_report` event was created for each, and an `emergency_meeting`
   event fired automatically on the 3rd, exactly per the threshold rule.
   Confirmed notifications and activity log entries were created for each.
5. **Missed-deadline path** — backdated a real task's deadline directly in
   Postgres, completed it via the API, and confirmed `missed_deadlines`
   incremented, `manager_satisfaction` dropped, and a `deadline_changed`
   event was created.
6. **Meetings** — confirmed `PATCH .../meetings/{id}/complete` persists
   notes/attendance/action_items and flips `completed` to `true`.
7. **Notifications / Activity Log / Timeline** — confirmed notifications
   and activity log entries were created by chat, bug reports, and
   workflow-engine rule firings; confirmed the timeline endpoint merges
   messages, events, and meetings into one chronologically sorted feed
   (verified `timestamps == sorted(timestamps)`).
8. **WebSocket real-time push** — connected a real Python `websockets`
   client to `/ws/companies/{id}?token=...`, then triggered a task status
   change via a separate REST call, and confirmed the WS client received
   `{"type": "task_updated", "data": {...}}` within ~1.5 seconds.
9. **Full pytest suite** — 9 original Phase 1/2 tests plus 8 new Phase 3
   tests (`tests/test_phase3.py`), **17/17 passing**, all against a real
   Postgres database. Covers: team generation, meeting generation, manager
   chat + history persistence, teammate chat, the bug→emergency-meeting
   escalation threshold, the missed-deadline satisfaction drop, timeline
   aggregation/ordering, and meeting completion.
10. **Frontend** — `npm run build` succeeded (1122 modules, no errors)
    after adding the Chat page, Timeline page, notifications bell, the
    WebSocket hook, and the bug-report action in the task drawer. Every
    field the new pages read (`MessageRead`, `TimelineEntry`,
    `MeetingRead`, `NotificationRead`, `TeamMemberRead`) was checked
    against real API responses via curl — no mismatches found.

### What was NOT run for Phase 3

- No headless browser, so the Chat/Timeline pages' actual rendering,
  the notifications bell dropdown interaction, and the WebSocket hook's
  reconnect-with-backoff logic were verified by code review + confirmed
  data contracts, not by clicking through a real browser session. Run
  `npm run dev` and click through Chat/Timeline yourself as the first
  visual check.
- Real Gemini calls remain untested (same as Phases 1-2) — only
  `MockAIService`'s new chat-reply branches were exercised.
- The APScheduler high-stress check-in job's *scheduling* (i.e., waiting
  a full 60 seconds for it to fire on its own) was not observed end-to-end
  in this session, though the job function itself follows the same
  query/notify/broadcast pattern already verified working in the
  bug-report and workflow-engine paths, and the app startup log
  confirmed the scheduler started without error.
