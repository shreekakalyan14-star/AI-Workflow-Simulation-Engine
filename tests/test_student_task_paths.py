"""
Member 2 — Task 2: Tests for personalized student task paths.

Proves that:
1. Two students on the same project can have different task paths
2. Tasks belong to the selected project
3. Sequence ordering is correct
4. Per-student status tracking works
"""
import uuid
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_test_db")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-to-the-shared-signing-secret")

from app.core.database import Base, engine as app_engine
from app.models.task import Task
from app.models.sprint import Sprint
from app.models.task_path import SimulationTaskPath
from app.models.enums import TaskStatus, TaskPriority, TaskType, DifficultyLevel, SprintStatus
from app.services.simulation.task_path_builder import (
    build_task_path,
    get_task_path,
    get_current_path_entry,
    get_canonical_tasks_for_project,
)
from app.core.database import SessionLocal


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Create a clean schema once per test session."""
    Base.metadata.create_all(bind=app_engine)
    yield
    with app_engine.begin() as conn:
        for table in reversed(Base.metadata.sorted_tables):
            conn.execute(text(f'DROP TABLE IF EXISTS {table.name} CASCADE'))


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def _seed_project_with_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3):
    """Create sprints and tasks for a project."""
    now = datetime.now(timezone.utc)
    task_ids = []
    for sprint_num in range(1, num_sprints + 1):
        sprint_id = uuid.uuid4()
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
            task_ids.append(task_id)
    db.commit()
    return task_ids


def _create_simulation(db, student_id, project_id, company_id):
    """Create a simulation record."""
    sim_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO simulations (id, student_id, company_id, project_id, title, description,
            role, difficulty, duration_weeks, status, progress, created_at, updated_at)
        VALUES (:id, :student_id, :company_id, :project_id, 'Test Simulation', 'Test',
            'Developer', 'INTERMEDIATE', 4, 'NOT_STARTED', 0, :now, :now)
    """), {
        "id": sim_id, "student_id": student_id,
        "company_id": company_id, "project_id": project_id,
        "now": now,
    })
    db.commit()
    return sim_id


def _create_company(db, student_id="test_student"):
    """Create a company record."""
    company_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO companies (id, name, industry, company_type, department, mission, description, student_id, created_at, updated_at)
        VALUES (:id, 'TestCo', 'Tech', 'STARTUP', 'Engineering', 'Test mission', 'Test company', :student_id, :now, :now)
    """), {"id": company_id, "student_id": student_id, "now": now})
    db.commit()
    return company_id


class TestPersonalizedTaskPaths:
    """Prove two students on the same project get different task paths."""

    def test_two_students_different_paths(self, db):
        """Student A gets all tasks, Student B gets a subset."""
        company_id = _create_company(db)
        project_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        db.execute(text("""
            INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
                status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
            VALUES (:id, :company_id, 'E-Commerce Platform', 'Developer', ARRAY['Python', 'FastAPI'],
                'INTERMEDIATE', 'PLANNING', ARRAY['Build API'], ARRAY['Auth'], ARRAY['Deployed API'],
                4, :now, :now)
        """), {"id": project_id, "company_id": company_id, "now": now})
        db.commit()

        all_task_ids = _seed_project_with_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3)
        assert len(all_task_ids) == 6

        sim_a = _create_simulation(db, "student_a", project_id, company_id)
        sim_b = _create_simulation(db, "student_b", project_id, company_id)

        # Student A gets all 6 tasks
        path_a = build_task_path(db, sim_a, project_id)
        assert len(path_a) == 6

        # Student B gets only the first 3 tasks (subset)
        subset_ids = all_task_ids[:3]
        path_b = build_task_path(db, sim_b, project_id, task_ids=subset_ids)
        assert len(path_b) == 3

        # Verify sequences are correct
        seq_a = [e.sequence for e in path_a]
        seq_b = [e.sequence for e in path_b]
        assert seq_a == [1, 2, 3, 4, 5, 6]
        assert seq_b == [1, 2, 3]

        # Verify all tasks belong to the same project
        for entry in path_a + path_b:
            task = db.get(Task, entry.task_id)
            assert task is not None
            sprint = db.get(Sprint, task.sprint_id)
            assert sprint.project_id == project_id

    def test_task_paths_are_independent(self, db):
        """Completing a task for Student A does not affect Student B."""
        company_id = _create_company(db)
        project_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        db.execute(text("""
            INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
                status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
            VALUES (:id, :company_id, 'Project X', 'Developer', ARRAY['Python'],
                'INTERMEDIATE', 'PLANNING', ARRAY['Goal'], ARRAY['Mod'], ARRAY['Deliv'],
                4, :now, :now)
        """), {"id": project_id, "company_id": company_id, "now": now})
        db.commit()

        task_ids = _seed_project_with_tasks(db, project_id, num_sprints=1, tasks_per_sprint=3)

        sim_a = _create_simulation(db, "student_a", project_id, company_id)
        sim_b = _create_simulation(db, "student_b", project_id, company_id)

        build_task_path(db, sim_a, project_id)
        build_task_path(db, sim_b, project_id)

        # Student A completes first task
        entry_a = get_current_path_entry(db, sim_a)
        assert entry_a is not None
        entry_a.status = TaskStatus.COMPLETED
        entry_a.completed_at = datetime.now(timezone.utc)
        db.commit()

        # Student B's first task is still BACKLOG
        entry_b = get_current_path_entry(db, sim_b)
        assert entry_b is not None
        assert entry_b.status == TaskStatus.BACKLOG

        # Student A's next task is still BACKLOG
        entries_a = get_task_path(db, sim_a)
        second_a = [e for e in entries_a if e.sequence == 2][0]
        assert second_a.status == TaskStatus.BACKLOG

    def test_progress_calculation_per_student(self, db):
        """Progress is calculated per student's own path."""
        company_id = _create_company(db)
        project_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        db.execute(text("""
            INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
                status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
            VALUES (:id, :company_id, 'Project Y', 'Developer', ARRAY['Python'],
                'INTERMEDIATE', 'PLANNING', ARRAY['Goal'], ARRAY['Mod'], ARRAY['Deliv'],
                4, :now, :now)
        """), {"id": project_id, "company_id": company_id, "now": now})
        db.commit()

        task_ids = _seed_project_with_tasks(db, project_id, num_sprints=1, tasks_per_sprint=4)

        sim_a = _create_simulation(db, "student_a", project_id, company_id)
        sim_b = _create_simulation(db, "student_b", project_id, company_id)

        # Student A gets all 4 tasks, completes 2
        path_a = build_task_path(db, sim_a, project_id)
        for entry in path_a[:2]:
            entry.status = TaskStatus.COMPLETED
            entry.completed_at = datetime.now(timezone.utc)

        # Student B gets 2 tasks, completes 1
        path_b = build_task_path(db, sim_b, project_id, task_ids=task_ids[:2])
        path_b[0].status = TaskStatus.COMPLETED
        path_b[0].completed_at = datetime.now(timezone.utc)
        db.commit()

        # Recalculate and verify
        entries_a = get_task_path(db, sim_a)
        completed_a = sum(1 for e in entries_a if e.status == TaskStatus.COMPLETED)
        assert completed_a == 2

        entries_b = get_task_path(db, sim_b)
        completed_b = sum(1 for e in entries_b if e.status == TaskStatus.COMPLETED)
        assert completed_b == 1

    def test_get_canonical_tasks_for_project(self, db):
        """Canonical tasks are ordered by sprint then sequence."""
        company_id = _create_company(db)
        project_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        db.execute(text("""
            INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
                status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
            VALUES (:id, :company_id, 'Project Z', 'Developer', ARRAY['Python'],
                'INTERMEDIATE', 'PLANNING', ARRAY['Goal'], ARRAY['Mod'], ARRAY['Deliv'],
                4, :now, :now)
        """), {"id": project_id, "company_id": company_id, "now": now})
        db.commit()

        task_ids = _seed_project_with_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3)
        tasks = get_canonical_tasks_for_project(db, project_id)
        assert len(tasks) == 6

        # Verify ordering: sprint 1 tasks first, then sprint 2
        sprint_ids_seen = []
        for t in tasks:
            sprint = db.get(Sprint, t.sprint_id)
            sprint_ids_seen.append(sprint.sprint_number)
        assert sprint_ids_seen == [1, 1, 1, 2, 2, 2]

    def test_sequence_unique_per_simulation(self, db):
        """Sequence numbers are unique within a simulation's task path."""
        company_id = _create_company(db)
        project_id = uuid.uuid4()
        now = datetime.now(timezone.utc)
        db.execute(text("""
            INSERT INTO projects (id, company_id, title, role, technology_stack, difficulty,
                status, objectives, modules, deliverables, duration_weeks, created_at, updated_at)
            VALUES (:id, :company_id, 'Project W', 'Developer', ARRAY['Python'],
                'INTERMEDIATE', 'PLANNING', ARRAY['Goal'], ARRAY['Mod'], ARRAY['Deliv'],
                4, :now, :now)
        """), {"id": project_id, "company_id": company_id, "now": now})
        db.commit()

        _seed_project_with_tasks(db, project_id, num_sprints=3, tasks_per_sprint=2)
        sim_id = _create_simulation(db, "student_x", project_id, company_id)

        path = build_task_path(db, sim_id, project_id)
        sequences = [e.sequence for e in path]
        assert len(sequences) == len(set(sequences)), "Duplicate sequences found"
        assert sequences == sorted(sequences), "Sequences not in order"
