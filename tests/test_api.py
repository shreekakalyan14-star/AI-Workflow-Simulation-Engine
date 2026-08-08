"""
API tests against a real Postgres database (see conftest.py) — no mocking of
the DB layer. Covers Features 1-5: generation, reads, Kanban board, task
lifecycle + dependency enforcement, and multi-tenant access control.
"""


def _generate(client, auth_headers, student_id="student_001"):
    resp = client.post(
        "/api/generate",
        headers=auth_headers,
        json={
            "student_id": student_id,
            "role": "Backend Developer",
            "technology_stack": ["Python", "FastAPI", "PostgreSQL"],
            "difficulty": "intermediate",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_generate_creates_full_simulation(client, auth_headers):
    data = _generate(client, auth_headers)
    assert data["task_count"] > 0
    assert len(data["sprint_ids"]) == 4


def test_generate_rejects_mismatched_student_id(client, auth_headers):
    resp = client.post(
        "/api/generate",
        headers=auth_headers,
        json={
            "student_id": "someone_else",
            "role": "Backend Developer",
            "technology_stack": ["Python"],
            "difficulty": "beginner",
            "company_type": "startup",
        },
    )
    assert resp.status_code == 403


def test_company_and_manager_readable(client, auth_headers):
    data = _generate(client, auth_headers)
    company_id = data["company_id"]

    company_resp = client.get(f"/api/companies/{company_id}", headers=auth_headers)
    assert company_resp.status_code == 200
    assert company_resp.json()["name"]

    manager_resp = client.get(f"/api/companies/{company_id}/manager", headers=auth_headers)
    assert manager_resp.status_code == 200
    assert manager_resp.json()["personality"] in {
        "strict", "friendly", "corporate", "startup_founder",
    }


def test_project_and_state_readable(client, auth_headers):
    data = _generate(client, auth_headers)
    project_id = data["project_id"]

    project_resp = client.get(f"/api/projects/{project_id}", headers=auth_headers)
    assert project_resp.status_code == 200
    body = project_resp.json()
    assert len(body["modules"]) > 0
    assert len(body["deliverables"]) > 0

    state_resp = client.get(f"/api/projects/{project_id}/state", headers=auth_headers)
    assert state_resp.status_code == 200
    assert state_resp.json()["current_sprint_number"] == 1


def test_kanban_board_groups_all_tasks(client, auth_headers):
    data = _generate(client, auth_headers)
    project_id = data["project_id"]

    board_resp = client.get(f"/api/projects/{project_id}/board", headers=auth_headers)
    assert board_resp.status_code == 200
    board = board_resp.json()
    total = sum(len(v) for v in board.values())
    assert total == data["task_count"]
    assert total == len(board["backlog"])  # everything starts in backlog


def test_task_dependency_blocks_start_until_anchor_completed(client, auth_headers):
    data = _generate(client, auth_headers)
    project_id = data["project_id"]

    board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
    dependent = next(t for t in board["backlog"] if t["depends_on_task_ids"])
    anchor_id = dependent["depends_on_task_ids"][0]

    # Cannot start the dependent task yet.
    blocked_resp = client.patch(
        f"/api/tasks/{dependent['id']}/status", headers=auth_headers, json={"status": "in_progress"}
    )
    assert blocked_resp.status_code == 409

    # Complete the anchor task.
    start_anchor = client.patch(
        f"/api/tasks/{anchor_id}/status", headers=auth_headers, json={"status": "in_progress"}
    )
    assert start_anchor.status_code == 200
    complete_anchor = client.patch(
        f"/api/tasks/{anchor_id}/status", headers=auth_headers, json={"status": "completed"}
    )
    assert complete_anchor.status_code == 200

    # Now the dependent task can start.
    unblocked_resp = client.patch(
        f"/api/tasks/{dependent['id']}/status", headers=auth_headers, json={"status": "in_progress"}
    )
    assert unblocked_resp.status_code == 200
    assert unblocked_resp.json()["status"] == "in_progress"

    # Project state reflects the completed task.
    state = client.get(f"/api/projects/{project_id}/state", headers=auth_headers).json()
    assert state["completed_tasks"] == 1


def test_cross_tenant_access_is_forbidden(client, auth_headers, other_auth_headers):
    data = _generate(client, auth_headers)
    company_id = data["company_id"]

    resp = client.get(f"/api/companies/{company_id}", headers=other_auth_headers)
    assert resp.status_code == 403


def test_missing_token_is_unauthorized(client):
    resp = client.get("/api/companies")
    assert resp.status_code == 401
