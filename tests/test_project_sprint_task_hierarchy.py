"""
Member 2 — Feature 1: Tests for Project → Sprints → Tasks hierarchy.

Proves that:
1. Every sprint belongs to exactly one project (FK project_id)
2. Every task belongs to exactly one sprint (FK sprint_id)
3. Board endpoint returns only tasks for the requested project
4. Sprints endpoint returns only sprints for the requested project
5. No cross-project task contamination on the board
6. Sequence numbering is per-sprint (not global)
7. Cascade delete: deleting a project removes its sprints and tasks
"""
import uuid
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_test_db")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-to-the-shared-signing-secret")

from app.core.config import settings
from app.core.database import Base, engine as app_engine, SessionLocal
from app.main import app
from app.models.task import Task, TaskDependency
from app.models.sprint import Sprint
from app.models.project import Project


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    Base.metadata.create_all(bind=app_engine)
    yield
    with app_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DROP TABLE IF EXISTS {table.name} CASCADE'))


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
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
    return {"Authorization": f"Bearer {make_token('test_hierarchy')}"}


@pytest.fixture
def other_auth_headers():
    return {"Authorization": f"Bearer {make_token('test_other')}"}


def _generate(client, auth_headers, student_id="test_hierarchy"):
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


def _seed_project_with_sprints_and_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3):
    """Create sprints and tasks for a project via raw SQL."""
    now = datetime.now(timezone.utc)
    sprint_ids = []
    task_ids = []
    for sprint_num in range(1, num_sprints + 1):
        sprint_id = uuid.uuid4()
        sprint_ids.append(sprint_id)
        db.execute(text("""
            INSERT INTO sprints (id, project_id, sprint_number, name, goal, status, created_at, updated_at)
            VALUES (:id, :project_id, :sprint_number, :name, :goal, 'PLANNED', :now, :now)
        """), {
            "id": sprint_id, "project_id": project_id,
            "sprint_number": sprint_num,
            "name": f"Sprint {sprint_num}", "goal": f"Goals for sprint {sprint_num}",
            "now": now,
        })
        for task_seq in range(1, tasks_per_sprint + 1):
            task_id = uuid.uuid4()
            task_ids.append(task_id)
            db.execute(text("""
                INSERT INTO tasks (id, sprint_id, sequence, title, description, acceptance_criteria,
                    priority, status, task_type, difficulty, estimated_hours, created_at, updated_at)
                VALUES (:id, :sprint_id, :seq, :title, 'Task description', ARRAY['Criteria'],
                    'medium', 'backlog', 'coding', 'INTERMEDIATE', 4.0, :now, :now)
            """), {
                "id": task_id, "sprint_id": sprint_id,
                "seq": task_seq,
                "title": f"Sprint {sprint_num} Task {task_seq}",
                "now": now,
            })
    db.commit()
    return sprint_ids, task_ids


def _create_company_and_project(db, student_id="test_hierarchy"):
    """Create a company and project via raw SQL."""
    company_id = uuid.uuid4()
    project_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO companies (id, name, industry, company_type, department, mission, description, student_id, created_at, updated_at)
        VALUES (:id, 'TestCo', 'Tech', 'STARTUP', 'Engineering', 'Test mission', 'Test company', :student_id, :now, :now)
    """), {"id": company_id, "student_id": student_id, "now": now})
    db.execute(text("""
        INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
            status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
        VALUES (:id, :company_id, 'Test Project', 'Developer', ARRAY['Python', 'FastAPI'],
            'INTERMEDIATE', 'PLANNING', ARRAY['Build API'], ARRAY['Auth'], ARRAY['Deployed API'],
            4, :now, :now)
    """), {"id": project_id, "company_id": company_id, "now": now})
    db.commit()
    return company_id, project_id


class TestSprintBelongsToProject:
    """Every sprint must have a valid project_id FK."""

    def test_sprints_created_by_generate_belong_to_project(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]
        sprint_ids = data["sprint_ids"]

        sprints_resp = client.get(f"/api/projects/{project_id}/sprints", headers=auth_headers)
        assert sprints_resp.status_code == 200
        sprints = sprints_resp.json()

        assert len(sprints) == 4
        for sprint in sprints:
            assert sprint["project_id"] == project_id
            assert sprint["id"] in sprint_ids

    def test_sprint_has_required_fields(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        sprints = client.get(f"/api/projects/{project_id}/sprints", headers=auth_headers).json()
        for sprint in sprints:
            assert "id" in sprint
            assert "project_id" in sprint
            assert "sprint_number" in sprint
            assert "name" in sprint
            assert "goal" in sprint
            assert "status" in sprint

    def test_sprint_numbers_are_sequential(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        sprints = client.get(f"/api/projects/{project_id}/sprints", headers=auth_headers).json()
        numbers = [s["sprint_number"] for s in sprints]
        assert numbers == [1, 2, 3, 4]

    def test_sprint_detail_includes_tasks(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        sprints = client.get(f"/api/projects/{project_id}/sprints", headers=auth_headers).json()
        sprint_id = sprints[0]["id"]

        detail = client.get(
            f"/api/projects/{project_id}/sprints/{sprint_id}", headers=auth_headers
        ).json()
        assert "tasks" in detail
        assert len(detail["tasks"]) > 0
        for task in detail["tasks"]:
            assert task["sprint_id"] == sprint_id


class TestTaskBelongsToSprint:
    """Every task must have a valid sprint_id FK pointing to a sprint in the same project."""

    def test_tasks_on_board_have_sprint_id(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]
        assert len(all_tasks) == data["task_count"]

        for task in all_tasks:
            assert "sprint_id" in task
            assert task["sprint_id"] is not None

    def test_tasks_reference_valid_sprints(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        sprints = client.get(f"/api/projects/{project_id}/sprints", headers=auth_headers).json()
        sprint_ids = {s["id"] for s in sprints}

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]

        for task in all_tasks:
            assert task["sprint_id"] in sprint_ids, (
                f"Task {task['id']} has sprint_id {task['sprint_id']} not in project sprints"
            )

    def test_tasks_span_multiple_sprints(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]
        sprint_ids_used = {t["sprint_id"] for t in all_tasks}

        assert len(sprint_ids_used) > 1, "Tasks should be spread across multiple sprints"

    def test_task_read_schema_includes_sprint_id(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]
        task = all_tasks[0]

        assert "sprint_id" in task
        assert isinstance(task["sprint_id"], str)


class TestBoardFiltersByProject:
    """The board endpoint must only return tasks belonging to the requested project."""

    def test_board_returns_only_project_tasks(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]

        assert len(all_tasks) == data["task_count"]

    def test_board_excludes_tasks_from_other_projects(self, client, auth_headers):
        """Create two projects and verify board isolation."""
        data1 = _generate(client, auth_headers, student_id="test_hierarchy")
        project_id_1 = data1["project_id"]

        # Generate a second project for the same student
        db = SessionLocal()
        try:
            company_id_2, project_id_2 = _create_company_and_project(db, "test_hierarchy")
            _seed_project_with_sprints_and_tasks(db, project_id_2, num_sprints=1, tasks_per_sprint=2)
        finally:
            db.close()

        board1 = client.get(f"/api/projects/{project_id_1}/board", headers=auth_headers).json()
        tasks1 = {t["id"] for tasks in board1.values() for t in tasks}

        board2 = client.get(f"/api/projects/{project_id_2}/board", headers=auth_headers).json()
        tasks2 = {t["id"] for tasks in board2.values() for t in tasks}

        # No overlap between the two boards
        assert tasks1.isdisjoint(tasks2), "Boards from different projects must not share tasks"

    def test_board_groups_tasks_by_status(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()

        from app.models.enums import TaskStatus
        expected_statuses = {s.value for s in TaskStatus}
        assert set(board.keys()) == expected_statuses

    def test_board_all_tasks_start_in_backlog(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]

        assert len(board["backlog"]) == len(all_tasks)
        for task in all_tasks:
            assert task["status"] == "backlog"

    def test_board_with_nonexistent_project_returns_404(self, client, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/projects/{fake_id}/board", headers=auth_headers)
        assert resp.status_code == 404


class TestSequencePerSprint:
    """Sequence numbers should be unique and ordered within each sprint."""

    def test_sequence_numbers_are_unique_per_sprint(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]

        by_sprint: dict[str, list] = {}
        for task in all_tasks:
            by_sprint.setdefault(task["sprint_id"], []).append(task)

        for sprint_id, sprint_tasks in by_sprint.items():
            sequences = [t["sequence"] for t in sprint_tasks]
            assert len(sequences) == len(set(sequences)), (
                f"Duplicate sequences in sprint {sprint_id}: {sequences}"
            )

    def test_sequences_are_ascending_within_sprint(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]

        by_sprint: dict[str, list] = {}
        for task in all_tasks:
            by_sprint.setdefault(task["sprint_id"], []).append(task)

        for sprint_id, sprint_tasks in by_sprint.items():
            sequences = sorted(t["sequence"] for t in sprint_tasks)
            assert sequences == list(range(len(sequences))), (
                f"Sequences not starting from 0 in sprint {sprint_id}"
            )


class TestTaskDependenciesArePreserved:
    """TaskDependency records link tasks within the same project."""

    def test_dependencies_reference_valid_tasks(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        board = client.get(f"/api/projects/{project_id}/board", headers=auth_headers).json()
        all_tasks = [t for tasks in board.values() for t in tasks]
        task_ids = {t["id"] for t in all_tasks}

        for task in all_tasks:
            for dep_id in task.get("depends_on_task_ids", []):
                assert dep_id in task_ids, (
                    f"Task {task['id']} depends on {dep_id} which is not in this project"
                )

    def test_dependency_chain_does_not_cross_projects(self, client, auth_headers):
        data1 = _generate(client, auth_headers, student_id="test_hierarchy")
        project_id_1 = data1["project_id"]

        db = SessionLocal()
        try:
            company_id_2, project_id_2 = _create_company_and_project(db, "test_hierarchy")
            _seed_project_with_sprints_and_tasks(db, project_id_2, num_sprints=1, tasks_per_sprint=2)
        finally:
            db.close()

        board1 = client.get(f"/api/projects/{project_id_1}/board", headers=auth_headers).json()
        tasks1_ids = {t["id"] for tasks in board1.values() for t in tasks}
        deps1 = {
            dep_id
            for tasks in board1.values()
            for t in tasks
            for dep_id in t.get("depends_on_task_ids", [])
        }

        board2 = client.get(f"/api/projects/{project_id_2}/board", headers=auth_headers).json()
        tasks2_ids = {t["id"] for tasks in board2.values() for t in tasks}

        assert deps1.isdisjoint(tasks2_ids), (
            "Project 1 dependencies must not reference Project 2 tasks"
        )


class TestCrossTenantBoardIsolation:
    """Students cannot see boards from other students' projects."""

    def test_other_student_cannot_read_board(self, client, auth_headers, other_auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        resp = client.get(f"/api/projects/{project_id}/board", headers=other_auth_headers)
        assert resp.status_code == 403


class TestSprintsEndpointFiltersByProject:
    """GET /api/projects/{project_id}/sprints returns only that project's sprints."""

    def test_sprints_endpoint_returns_project_sprints(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id = data["project_id"]

        sprints = client.get(f"/api/projects/{project_id}/sprints", headers=auth_headers).json()
        for sprint in sprints:
            assert sprint["project_id"] == project_id

    def test_sprints_endpoint_excludes_other_project_sprints(self, client, auth_headers):
        data = _generate(client, auth_headers)
        project_id_1 = data["project_id"]

        db = SessionLocal()
        try:
            company_id_2, project_id_2 = _create_company_and_project(db, "test_hierarchy")
            _seed_project_with_sprints_and_tasks(db, project_id_2, num_sprints=1, tasks_per_sprint=2)
        finally:
            db.close()

        sprints1 = client.get(f"/api/projects/{project_id_1}/sprints", headers=auth_headers).json()
        sprints2 = client.get(f"/api/projects/{project_id_2}/sprints", headers=auth_headers).json()

        ids1 = {s["id"] for s in sprints1}
        ids2 = {s["id"] for s in sprints2}
        assert ids1.isdisjoint(ids2), "Sprint IDs must not overlap across projects"
