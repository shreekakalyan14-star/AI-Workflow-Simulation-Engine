"""
Phase 3 tests: AI Manager/Teammate chat, the stateful workflow engine's
bug/deadline escalation rules, meetings, notifications, activity log, and
the timeline aggregation. Same real-Postgres approach as test_api.py.
"""
from .test_api import _generate


def test_team_members_generated(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    resp = client.get(f"/api/companies/{data['company_id']}/team", headers=auth_headers)
    assert resp.status_code == 200
    members = resp.json()
    assert len(members) == 3
    assert all(m["skill_level"] > 0 for m in members)


def test_meetings_generated_for_every_sprint(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    resp = client.get(f"/api/projects/{data['project_id']}/meetings", headers=auth_headers)
    assert resp.status_code == 200
    meetings = resp.json()
    # 4 sprints * (planning + review) = 8
    assert len(meetings) == 8
    assert {m["meeting_type"] for m in meetings} == {"sprint_planning", "sprint_review"}


def test_manager_chat_replies_and_persists_history(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    company_id = data["company_id"]

    resp = client.post(
        f"/api/companies/{company_id}/chat/manager",
        headers=auth_headers,
        json={"content": "Just finished the setup task."},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["student_message"]["content"] == "Just finished the setup task."
    assert len(body["reply"]["content"]) > 0
    assert body["reply"]["sender_type"] == "manager"

    history = client.get(f"/api/companies/{company_id}/chat/manager", headers=auth_headers)
    assert history.status_code == 200
    assert len(history.json()) == 2


def test_team_chat_replies(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    company_id = data["company_id"]
    teammate_id = client.get(f"/api/companies/{company_id}/team", headers=auth_headers).json()[0]["id"]

    resp = client.post(
        f"/api/companies/{company_id}/chat/team/{teammate_id}",
        headers=auth_headers,
        json={"content": "Can you review my PR?"},
    )
    assert resp.status_code == 201
    assert resp.json()["reply"]["sender_type"] == "team_member"


def test_bug_reports_escalate_to_emergency_meeting_at_threshold(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    project_id = data["project_id"]
    board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
    task_ids = [t["id"] for t in board["backlog"][:3]]

    for i, task_id in enumerate(task_ids):
        resp = client.post(
            f"/api/tasks/{task_id}/report-bug", headers=auth_headers, json={"description": f"bug {i}"}
        )
        assert resp.status_code == 201

    events = client.get(f"/api/projects/{project_id}/events", headers=auth_headers).json()
    event_types = [e["event_type"] for e in events]
    assert event_types.count("bug_report") == 3
    assert "emergency_meeting" in event_types

    state = client.get(f"/api/projects/{project_id}/state", headers=auth_headers).json()
    assert state["bug_count"] == 3

    notifications = client.get(f"/api/companies/{data['company_id']}/notifications", headers=auth_headers).json()
    assert len(notifications) >= 3


def test_missed_deadline_reduces_manager_satisfaction(client, auth_headers):
    import os
    from datetime import datetime, timedelta, timezone
    from sqlalchemy import create_engine, text

    data = _generate(client, auth_headers, student_id="student_001")
    project_id = data["project_id"]
    board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
    task_id = next(t["id"] for t in board["backlog"] if not t["depends_on_task_ids"])

    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as conn:
        conn.execute(
            text("UPDATE tasks SET deadline = :deadline WHERE id = :id"),
            {"deadline": datetime.now(timezone.utc) - timedelta(days=1), "id": task_id},
        )

    before_state = client.get(f"/api/projects/{project_id}/state", headers=auth_headers).json()

    client.patch(f"/api/tasks/{task_id}/status", headers=auth_headers, json={"status": "in_progress"})
    client.patch(f"/api/tasks/{task_id}/status", headers=auth_headers, json={"status": "completed"})

    after_state = client.get(f"/api/projects/{project_id}/state", headers=auth_headers).json()
    assert after_state["missed_deadlines"] == before_state["missed_deadlines"] + 1
    assert after_state["manager_satisfaction"] < before_state["manager_satisfaction"]

    events = client.get(f"/api/projects/{project_id}/events", headers=auth_headers).json()
    assert any(e["event_type"] == "deadline_changed" for e in events)


def test_timeline_aggregates_multiple_sources(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    company_id, project_id = data["company_id"], data["project_id"]

    client.post(
        f"/api/companies/{company_id}/chat/manager", headers=auth_headers, json={"content": "hello"}
    )
    board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
    task_id = next(t["id"] for t in board["backlog"] if not t["depends_on_task_ids"])
    client.patch(f"/api/tasks/{task_id}/status", headers=auth_headers, json={"status": "in_progress"})
    client.patch(f"/api/tasks/{task_id}/status", headers=auth_headers, json={"status": "completed"})

    timeline = client.get(f"/api/projects/{project_id}/timeline", headers=auth_headers).json()
    kinds = {e["kind"] for e in timeline}
    assert "message" in kinds
    assert "meeting" in kinds
    assert "task_completed" in kinds

    # chronological order
    timestamps = [e["timestamp"] for e in timeline]
    assert timestamps == sorted(timestamps)


def test_meeting_can_be_completed(client, auth_headers):
    data = _generate(client, auth_headers, student_id="student_001")
    project_id = data["project_id"]
    meeting_id = client.get(f"/api/projects/{project_id}/meetings", headers=auth_headers).json()[0]["id"]

    resp = client.patch(
        f"/api/projects/{project_id}/meetings/{meeting_id}/complete",
        headers=auth_headers,
        json={"notes": "Went well", "attendance": ["student_001"], "action_items": ["Ship it"]},
    )
    assert resp.status_code == 200
    assert resp.json()["completed"] is True
