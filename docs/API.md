# API Reference

Full interactive docs (Swagger) at **`/docs`**, ReDoc at **`/redoc`**, raw
OpenAPI schema at **`/openapi.json`** — auto-generated from the FastAPI
routes and Pydantic schemas, always in sync with the code.

All endpoints below require `Authorization: Bearer <jwt>`. The JWT must be
signed with `JWT_SECRET_KEY` and carry a `sub` (or `student_id`) claim.

## Dev-only

### `POST /api/dev/token`

Returns `404` unless `ENVIRONMENT=development`. Mints a JWT signed with
`JWT_SECRET_KEY` for local/standalone testing — this is what the frontend's
sign-in screen calls. Body: `{"student_id": "student_001", "role": "student"}`.
Response: `{"access_token": "...", "token_type": "bearer"}`. Remove or keep
disabled once Module 1's real auth is wired in.

## Generation

### `POST /api/generate`

Body:
```json
{
  "student_id": "student_001",
  "role": "Backend Developer",
  "technology_stack": ["Python", "FastAPI", "PostgreSQL"],
  "difficulty": "intermediate",
  "company_type": "startup"
}
```
`difficulty` ∈ `beginner | intermediate | advanced | expert`.
`company_type` ∈ `startup | product_company | mnc | healthcare | banking | ecommerce | education`.

`student_id` in the body must match the JWT subject, or the request is
rejected with `403`.

Response (`201`):
```json
{
  "company_id": "uuid",
  "project_id": "uuid",
  "sprint_ids": ["uuid", "uuid", "uuid", "uuid"],
  "task_count": 9
}
```

This single call generates and persists: the company, its manager, the
project, all 4 sprints, and every task with dependencies — atomically (one
DB transaction; failure anywhere rolls back everything).

## Companies

- `GET /api/companies` — list all companies owned by the authenticated student.
- `GET /api/companies/{company_id}` — one company.
- `GET /api/companies/{company_id}/manager` — that company's manager.

## Projects

- `GET /api/projects` — list all projects owned by the authenticated student.
- `GET /api/projects/{project_id}` — one project (title, objectives, modules, deliverables, etc).
- `GET /api/projects/{project_id}/state` — live `ProjectState` (completed/pending task counts, stress level, satisfaction scores, etc).

## Sprints

- `GET /api/projects/{project_id}/sprints` — all 4 sprints for a project.
- `GET /api/projects/{project_id}/sprints/{sprint_id}` — one sprint, including its tasks.

## Tasks / Kanban

- `GET /api/projects/{project_id}/board` — every task for the project,
  grouped by status (`backlog | todo | in_progress | review | blocked |
  completed`) — this is the direct data source for the Kanban board's
  columns.
- `GET /api/tasks/{task_id}` — one task, including its dependency IDs.
- `PATCH /api/tasks/{task_id}/status` — the single endpoint that drives
  drag-and-drop moves and the start/pause/complete/block actions:
  ```json
  { "status": "in_progress" }
  { "status": "blocked", "blocked_reason": "waiting on API key" }
  { "status": "completed", "deliverable_url": "https://github.com/..." }
  ```
  - Moving to `in_progress` from `backlog` is rejected with `409` if any
    dependency task isn't `completed` yet.
  - Moving to `completed` stamps `completed_at`, updates
    `missed_deadlines` if past the deadline, updates the project's rolling
    `avg_completion_time_hours`, and recomputes `pending_tasks` — all in
    the same request.

## Chat (Features 6 & 7)

- `GET /api/companies/{company_id}/chat/manager` — manager chat history.
- `POST /api/companies/{company_id}/chat/manager` — send a message; returns
  `{student_message, reply}`. The reply is generated in-character,
  grounded in the live `ProjectState`.
- `GET /api/companies/{company_id}/chat/team/{team_member_id}` — team chat
  history (see the known-simplification note in the root README — this
  returns all student+teammate messages for the company, not a strictly
  per-teammate thread).
- `POST /api/companies/{company_id}/chat/team/{team_member_id}` — send a
  message to a specific AI teammate; returns `{student_message, reply}`.

## Team

- `GET /api/companies/{company_id}/team` — the 3 generated AI teammates.

## Bug reports (feeds Features 8 & 9)

- `POST /api/tasks/{task_id}/report-bug` — body `{"description": "..."}`.
  Increments `ProjectState.bug_count`, fires a `bug_report` event, and
  fires an `emergency_meeting` event every 3rd bug.

## Events (Feature 9)

- `GET /api/projects/{project_id}/events` — all events for a project,
  newest first.
- `POST /api/projects/{project_id}/events/trigger` — manually fire an
  event (`event_type` one of `requirement_change | client_feedback |
  bug_report | code_review | sprint_planning | sprint_review |
  production_failure | database_change | security_audit |
  deadline_changed | emergency_meeting`, optional `description`). Useful
  for demos/testing without waiting for an automatic trigger.

## Meetings (Feature 10)

- `GET /api/projects/{project_id}/meetings` — all 8 auto-scheduled
  meetings (Sprint Planning + Sprint Review per sprint).
- `PATCH /api/projects/{project_id}/meetings/{meeting_id}/complete` — body
  `{"notes": "...", "attendance": [...], "action_items": [...]}`.

## Timeline (Feature 11)

- `GET /api/projects/{project_id}/timeline` — completed tasks + events +
  meetings + chat messages merged into one chronological feed. Each entry:
  `{"kind": "task_completed"|"event"|"meeting"|"message", "title", "detail", "timestamp"}`.

## Notifications (Feature 12)

- `GET /api/companies/{company_id}/notifications` — newest first.
- `PATCH /api/companies/{company_id}/notifications/{notification_id}/read`

## Activity Log (Feature 13)

- `GET /api/companies/{company_id}/activity` — last 200 entries, newest first.

## WebSocket (Feature 17)

- `ws://.../ws/companies/{company_id}?token=<jwt>` — pushes
  `{"type": "chat_message"|"task_updated"|"bug_reported"|"event"|"notification", "data": {...}}`
  frames live. Token is passed as a query parameter because browsers can't
  set custom headers on the WS handshake; it's validated the same way as
  the REST bearer token, and the connection is rejected (`4401`/`4403`) if
  invalid or if it doesn't belong to the requesting student's company.

## Errors

Standard FastAPI/Pydantic validation errors (`422`) for malformed bodies;
`401` for missing/invalid tokens; `403` for valid-but-not-yours resources;
`404` for resources that don't exist; `409` for the dependency-ordering
conflict described above.
