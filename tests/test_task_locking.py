"""
Member 2 — Task 4: Tests for current-task-only access (task locking).

Proves that:
1. Current task can be started
2. Future tasks cannot be started (403)
3. Completed tasks cannot be re-started (403)
4. API cannot bypass locking via direct task_id
5. Board endpoint includes lock status
"""
import uuid
import os
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_test_db")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-to-the-shared-signing-secret")

from app.core.config import settings
from app.core.database import Base, engine as app_engine, SessionLocal
from app.main import app
from app.models.enums import (
    TaskStatus, TaskPriority, TaskType, DifficultyLevel,
    SprintStatus, SimulationStatus, ScenarioStatus, ProjectStatus, CompanyType,
)
from app.models.task import Task
from app.models.sprint import Sprint
from app.models.task_path import SimulationTaskPath
from app.models.simulation import Simulation, Scenario


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


@pytest.fixture
def auth_headers():
    return {"Authorization": f"Bearer {make_token('test_student')}"}


def _generate(client, auth_headers, student_id="test_student"):
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


def _create_simulation_via_db(client, auth_headers, student_id="test_student"):
    gen_data = _generate(client, auth_headers, student_id)
    company_id = gen_data["company_id"]
    project_id = gen_data["project_id"]

    db = SessionLocal()
    try:
        sim_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        db.execute(text("""
            INSERT INTO simulations (id, student_id, company_id, project_id, title, description, role, difficulty, duration_weeks, status, started_at, completed_at, current_scenario_id, current_task_id, progress, created_at, updated_at)
            VALUES (:id, :student_id, :company_id, :project_id, 'Backend Developer Internship', 'Full stack developer simulation', 'Backend Developer', 'INTERMEDIATE', 4, 'NOT_STARTED', NULL, NULL, NULL, NULL, 0, :now, :now)
        """), {
            "id": sim_id, "student_id": student_id,
            "company_id": company_id, "project_id": project_id,
            "now": now,
        })

        task_id = str(uuid.uuid4())
        sprint_result = db.execute(text("SELECT id FROM sprints LIMIT 1")).fetchone()
        sprint_id = str(sprint_result[0]) if sprint_result else None
        if sprint_id:
            db.execute(text("""
                INSERT INTO tasks (id, sprint_id, sequence, title, description, acceptance_criteria, priority, status, task_type, difficulty, estimated_hours, created_at, updated_at)
                VALUES (:id, :sprint_id, 0, 'Build Employee API', 'Build an employee CRUD API', ARRAY['Returns JSON', 'Handles errors'], 'medium', 'backlog', 'api_development', 'INTERMEDIATE', 4.0, :now, :now)
            """), {"id": task_id, "sprint_id": sprint_id, "now": now})

        scenario_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO scenarios (id, simulation_id, sequence, title, description, workplace_context, role, difficulty, required_skills, objectives, status, sequence_order, created_at, updated_at)
            VALUES (:id, :sim_id, 1, 'Backend API Development', 'Build a RESTful API', 'Tech startup environment', 'Backend Developer', 'INTERMEDIATE', ARRAY['Python', 'FastAPI'], ARRAY['Build API'], 'PENDING', 1, :now, :now)
        """), {"id": scenario_id, "sim_id": sim_id, "now": now})

        link_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO scenario_tasks (id, scenario_id, task_id, sequence, created_at, updated_at)
            VALUES (:id, :scenario_id, :task_id, 1, :now, :now)
            ON CONFLICT DO NOTHING
        """), {"id": link_id, "scenario_id": scenario_id, "task_id": task_id, "now": now})

        db.commit()

        return {
            "simulation_id": sim_id,
            "company_id": company_id,
            "project_id": project_id,
            "scenario_id": scenario_id,
            "task_id": task_id,
        }
    finally:
        db.close()


def _start_and_get_current_task(client, auth_headers, sim_id):
    client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
    resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["task_id"]


class TestCurrentTaskUnlocking:
    def test_current_task_can_start(self, client, auth_headers):
        """Test: The current task can be started successfully."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == "in_progress"

    def test_current_task_can_submit(self, client, auth_headers):
        """Test: The current task can be submitted when in_progress."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "done"}'},
        )
        assert resp.status_code == 201


class TestFutureTaskLocking:
    def test_future_task_cannot_start(self, client, auth_headers):
        """Test: A task that is not the current task cannot be started (403)."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        # Start simulation — this sets current_task_id from task path
        _start_and_get_current_task(client, auth_headers, sim_id)

        # Try to start a random future task ID (not the current task)
        fake_task_id = str(uuid.uuid4())
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{fake_task_id}/start", headers=auth_headers)
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()

    def test_future_task_cannot_submit(self, client, auth_headers):
        """Test: A task that is not the current task cannot be submitted (403)."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        _start_and_get_current_task(client, auth_headers, sim_id)

        fake_task_id = str(uuid.uuid4())
        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{fake_task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{}'},
        )
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()

    def test_future_task_cannot_complete(self, client, auth_headers):
        """Test: A task that is not the current task cannot be completed (403)."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        _start_and_get_current_task(client, auth_headers, sim_id)

        fake_task_id = str(uuid.uuid4())
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{fake_task_id}/complete", headers=auth_headers)
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()


class TestApiCannotBypassLocking:
    def test_start_completed_task_rejected(self, client, auth_headers):
        """Test: Starting a completed task is rejected (403)."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        # Start and complete the task
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "done"}'},
        )

        # Try to start the same (now completed + no longer current) task again
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()

    def test_submit_completed_task_rejected(self, client, auth_headers):
        """Test: Submitting a completed task is rejected (403)."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]

        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "done"}'},
        )

        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "done again"}'},
        )
        assert resp.status_code == 403
        assert "locked" in resp.json()["detail"].lower()


class TestBoardLockStatus:
    def test_board_includes_lock_status(self, client, auth_headers):
        """Test: Board endpoint returns lock status when simulation_id is provided."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        project_id = data["project_id"]

        _start_and_get_current_task(client, auth_headers, sim_id)

        # Fetch board with simulation_id
        resp = client.get(
            f"/api/projects/{project_id}/board?simulation_id={sim_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        board = resp.json()

        # Flatten all tasks
        all_tasks = [t for tasks in board.values() for t in tasks]
        assert len(all_tasks) > 0

        # Each task should have a 'locked' field
        for t in all_tasks:
            assert "locked" in t, f"Task {t['id']} missing 'locked' field"

        # At least one task should be locked (the future ones)
        locked_tasks = [t for t in all_tasks if t.get("locked")]
        assert len(locked_tasks) > 0, "Expected at least one locked task"

    def test_board_without_simulation_id_no_lock_field(self, client, auth_headers):
        """Test: Board endpoint without simulation_id does not include lock status."""
        data = _create_simulation_via_db(client, auth_headers)
        project_id = data["project_id"]

        resp = client.get(f"/api/projects/{project_id}/board", headers=auth_headers)
        assert resp.status_code == 200
        board = resp.json()

        all_tasks = [t for tasks in board.values() for t in tasks]
        # Without simulation_id, tasks should not have 'locked' field
        for t in all_tasks:
            assert "locked" not in t, f"Task {t['id']} should not have 'locked' field without simulation_id"
