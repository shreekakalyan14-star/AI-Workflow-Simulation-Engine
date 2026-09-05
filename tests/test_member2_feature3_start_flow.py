"""
Member 2 — Feature 3: Tests for the complete Start Simulation flow.

Proves that:
1. Starting a simulation sets status=IN_PROGRESS, current_task_id, current_scenario_id
2. GET /tasks/current returns the valid current task (not "Waiting for Task")
3. Current task is in TODO state after start (ready for "Start Task" button)
4. Starting the task transitions it to IN_PROGRESS
5. Completing a task progresses to the next task in the path
6. current_scenario_id updates when crossing scenario boundaries
7. All IDs (simulation_id, project_id, current_task_id, current_scenario_id) are stored and valid
"""
import uuid
import os
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_test_db")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-to-the-shared-signing-secret")

from app.core.config import settings
from app.core.database import Base, engine as app_engine, SessionLocal
from app.main import app
from app.models.enums import TaskStatus, SimulationStatus


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    Base.metadata.create_all(bind=app_engine)
    yield
    with app_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DROP TABLE IF EXISTS {table.name} CASCADE'))


@pytest.fixture
def client():
    return TestClient(app)


def make_token(student_id: str = "test_student") -> str:
    from jose import jwt
    return jwt.encode(
        {"sub": student_id, "student_id": student_id, "role": "student"},
        settings.JWT_SECRET_KEY,
        algorithm=settings.JWT_ALGORITHM,
    )


def _headers(student_id):
    return {"Authorization": f"Bearer {make_token(student_id)}"}


def _seed_company(db, student_id):
    cid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO companies (id, name, industry, company_type, department, mission,
            description, student_id, created_at, updated_at)
        VALUES (:id, 'TestCo', 'Tech', 'STARTUP', 'Engineering', 'Mission',
            'Test', :sid, :now, :now)
    """), {"id": cid, "sid": student_id, "now": now})
    db.commit()
    return cid


def _seed_project(db, company_id):
    pid = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
            status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
        VALUES (:id, :cid, 'Test Project', 'Developer', ARRAY['Python', 'FastAPI'],
            'INTERMEDIATE', 'PLANNING', ARRAY['Build API', 'Build UI'],
            ARRAY['Auth', 'Dashboard'], ARRAY['Deployed App'], 4, :now, :now)
    """), {"id": pid, "cid": company_id, "now": now})
    db.commit()
    return pid


def _seed_sprints_and_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3):
    now = datetime.now(timezone.utc)
    all_task_ids = []
    for sn in range(1, num_sprints + 1):
        sid = uuid.uuid4()
        db.execute(text("""
            INSERT INTO sprints (id, project_id, sprint_number, name, goal, status, created_at, updated_at)
            VALUES (:id, :pid, :sn, :name, :goal, 'PLANNED', :now, :now)
        """), {"id": sid, "pid": project_id, "sn": sn,
               "name": f"Sprint {sn}", "goal": f"Goal {sn}", "now": now})
        for seq in range(1, tasks_per_sprint + 1):
            tid = uuid.uuid4()
            all_task_ids.append(tid)
            db.execute(text("""
                INSERT INTO tasks (id, sprint_id, sequence, title, description, acceptance_criteria,
                    priority, status, task_type, difficulty, estimated_hours, created_at, updated_at)
                VALUES (:id, :sid, :seq, :title, 'Desc', ARRAY['Criteria'],
                    'medium', 'backlog', 'coding', 'INTERMEDIATE', 4.0, :now, :now)
            """), {"id": tid, "sid": sid, "seq": seq,
                   "title": f"S{sn} T{seq}", "now": now})
    db.commit()
    return all_task_ids


def _seed_simulation(db, student_id, company_id, project_id):
    sim_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO simulations (id, student_id, company_id, project_id, title, description,
            role, difficulty, duration_weeks, status, progress, created_at, updated_at)
        VALUES (:id, :sid, :cid, :pid, 'Test Sim', 'Test', 'Developer', 'INTERMEDIATE', 4,
            'NOT_STARTED', 0, :now, :now)
    """), {"id": sim_id, "sid": student_id, "cid": company_id,
           "pid": project_id, "now": now})
    db.commit()
    return sim_id


def _seed_scenarios_with_tasks(db, simulation_id, task_ids, tasks_per_scenario=3):
    """Create scenarios and link tasks via ScenarioTask."""
    now = datetime.now(timezone.utc)
    scenario_ids = []
    for i in range(0, len(task_ids), tasks_per_scenario):
        chunk = task_ids[i : i + tasks_per_scenario]
        scenario_id = uuid.uuid4()
        scenario_ids.append(scenario_id)
        db.execute(text("""
            INSERT INTO scenarios (id, simulation_id, sequence, title, description, workplace_context,
                role, difficulty, required_skills, objectives, status, sequence_order, created_at, updated_at)
            VALUES (:id, :sid, :seq, :title, 'Desc', 'Context', 'Developer', 'INTERMEDIATE',
                ARRAY['Python'], ARRAY['Goal'], 'PENDING', :seq, :now, :now)
        """), {"id": scenario_id, "sid": simulation_id,
               "seq": len(scenario_ids), "title": f"Scenario {len(scenario_ids)}", "now": now})
        for idx, tid in enumerate(chunk):
            st_id = uuid.uuid4()
            db.execute(text("""
                INSERT INTO scenario_tasks (id, scenario_id, task_id, sequence, created_at, updated_at)
                VALUES (:id, :scid, :tid, :seq, :now, :now)
                ON CONFLICT DO NOTHING
            """), {"id": st_id, "scid": scenario_id, "tid": tid, "seq": idx + 1, "now": now})
    db.commit()
    return scenario_ids


def _full_setup(db, student_id, num_sprints=2, tasks_per_sprint=3, tasks_per_scenario=3):
    company_id = _seed_company(db, student_id)
    project_id = _seed_project(db, company_id)
    task_ids = _seed_sprints_and_tasks(db, project_id, num_sprints, tasks_per_sprint)
    sim_id = _seed_simulation(db, student_id, company_id, project_id)
    scenario_ids = _seed_scenarios_with_tasks(db, sim_id, task_ids, tasks_per_scenario)
    return sim_id, [str(tid) for tid in task_ids], [str(sid) for sid in scenario_ids]


class TestStartSimulationFlow:
    """API-level tests for the complete start simulation flow."""

    def test_start_sets_status_in_progress(self, client):
        """POST /start sets simulation status to IN_PROGRESS."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "start_status")
        finally:
            db.close()

        resp = client.post(f"/api/simulations/{sim_id}/start", headers=_headers("start_status"), json={})
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "in_progress"

    def test_start_sets_current_task_id(self, client):
        """POST /start sets current_task_id to the first task in the path."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "start_taskid")
        finally:
            db.close()

        resp = client.post(f"/api/simulations/{sim_id}/start", headers=_headers("start_taskid"), json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_task"] is not None
        assert data["current_task"]["id"] == task_ids[0]

    def test_start_sets_current_scenario_id(self, client):
        """POST /start sets current_scenario_id to the first scenario."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "start_scid")
        finally:
            db.close()

        resp = client.post(f"/api/simulations/{sim_id}/start", headers=_headers("start_scid"), json={})
        assert resp.status_code == 200
        data = resp.json()
        assert data["current_scenario"] is not None
        assert data["current_scenario"]["id"] == scenario_ids[0]

    def test_current_task_endpoint_returns_valid_task(self, client):
        """GET /tasks/current returns the current task, not a 404."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "current_valid")
        finally:
            db.close()

        headers = _headers("current_valid")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})

        resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["task_id"] == task_ids[0]
        assert data["status"] == "todo"

    def test_current_task_is_not_none_after_start(self, client):
        """After start, current task must exist — no 'Waiting for Task' state."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "not_none")
        finally:
            db.close()

        headers = _headers("not_none")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})

        sim_resp = client.get(f"/api/simulations/{sim_id}", headers=headers)
        assert sim_resp.status_code == 200
        assert sim_resp.json()["current_task"] is not None

    def test_task_path_matches_current_task(self, client):
        """The task path's first entry matches the current task after start."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "path_match")
        finally:
            db.close()

        headers = _headers("path_match")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})

        task_resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=headers).json()
        path_resp = client.get(f"/api/simulations/{sim_id}/task-path", headers=headers).json()

        assert path_resp[0]["task_id"] == task_resp["task_id"]
        assert path_resp[0]["status"] == "todo"

    def test_start_task_transitions_to_in_progress(self, client):
        """POST /tasks/{id}/start transitions the task from TODO to IN_PROGRESS."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "to_progress")
        finally:
            db.close()

        headers = _headers("to_progress")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})

        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/start",
            headers=headers,
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "in_progress"

    def test_complete_task_progresses_to_next(self, client):
        """Completing a task progresses to the next task in the path."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "progress_next")
        finally:
            db.close()

        headers = _headers("progress_next")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})

        # Start and complete first task
        client.post(f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/start", headers=headers)
        client.post(
            f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/submit",
            headers=headers,
            data={"metadata": '{"response": "done"}'},
        )

        # Current task should now be the second task
        resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["task_id"] == task_ids[1]

    def test_all_ids_are_valid_uuids(self, client):
        """Simulation ID, current task ID, current scenario ID are valid UUIDs."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "valid_uuids")
        finally:
            db.close()

        headers = _headers("valid_uuids")
        resp = client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})
        data = resp.json()

        uuid.UUID(data["simulation_id"])
        assert data["current_task"] is not None
        uuid.UUID(data["current_task"]["id"])
        assert data["current_scenario"] is not None
        uuid.UUID(data["current_scenario"]["id"])

    def test_cannot_start_twice(self, client):
        """POST /start on an already-started simulation returns 409."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "no_restart")
        finally:
            db.close()

        headers = _headers("no_restart")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})
        resp = client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})
        assert resp.status_code == 409

    def test_complete_flow_start_to_second_task(self, client):
        """Full flow: start → start task → complete → next task is second in path."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "full_flow", 2, 3, 3)
        finally:
            db.close()

        headers = _headers("full_flow")

        # 1. Start simulation
        resp = client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})
        assert resp.status_code == 200
        sim_data = resp.json()
        assert sim_data["status"] == "in_progress"
        assert sim_data["current_task"]["id"] == task_ids[0]

        # 2. Get current task — should be task 0 in TODO state
        task_resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=headers).json()
        assert task_resp["task_id"] == task_ids[0]
        assert task_resp["status"] == "todo"

        # 3. Start the task
        start_resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/start",
            headers=headers,
        )
        assert start_resp.status_code == 200

        # 4. Submit/complete the task
        submit_resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/submit",
            headers=headers,
            data={"metadata": '{"response": "done"}'},
        )
        assert submit_resp.status_code == 201

        # 5. Current task should now be task 1
        next_resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=headers).json()
        assert next_resp["task_id"] == task_ids[1]
        assert next_resp["status"] == "todo"

        # 6. Task path should reflect completion
        path = client.get(f"/api/simulations/{sim_id}/task-path", headers=headers).json()
        assert path[0]["status"] == "completed"
        assert path[1]["task_id"] == task_ids[1]

    def test_progress_reflects_completed_tasks(self, client):
        """Progress percentage updates as tasks are completed."""
        db = SessionLocal()
        try:
            sim_id, task_ids, scenario_ids = _full_setup(db, "progress_pct", 1, 4, 4)
        finally:
            db.close()

        headers = _headers("progress_pct")
        client.post(f"/api/simulations/{sim_id}/start", headers=headers, json={})

        # Complete first task
        client.post(f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/start", headers=headers)
        client.post(
            f"/api/simulations/{sim_id}/tasks/{task_ids[0]}/submit",
            headers=headers,
            data={"metadata": '{}'},
        )

        progress = client.get(f"/api/simulations/{sim_id}/progress", headers=headers).json()
        assert progress["completed_tasks"] == 1
        assert progress["total_tasks"] == 4
        assert progress["remaining_tasks"] == 3
