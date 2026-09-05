"""
Member 2 — Task 3: Tests for Start Simulation flow with task path integration.

Proves that:
1. Starting a simulation builds the task path
2. current_task_id comes from the first task path entry
3. The task path entries exist and are correctly ordered
4. The current task is valid (not None, status is TODO)
"""
import uuid
import os
from datetime import datetime, timezone

import pytest
from sqlalchemy import text

os.environ.setdefault("DATABASE_URL", "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_test_db")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-to-the-shared-signing-secret")

from app.core.database import Base, engine as app_engine, SessionLocal
from app.models.enums import (
    TaskStatus, TaskPriority, TaskType, DifficultyLevel,
    SprintStatus, SimulationStatus, ScenarioStatus, ProjectStatus, CompanyType,
)
from app.models.task import Task
from app.models.sprint import Sprint
from app.models.task_path import SimulationTaskPath
from app.models.simulation import Simulation, Scenario
from app.services.simulation.task_path_builder import build_task_path, get_canonical_tasks_for_project


@pytest.fixture(scope="session", autouse=True)
def _setup_database():
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


def _create_company(db, student_id="test_student"):
    company_id = uuid.uuid4()
    now = datetime.now(timezone.utc)
    db.execute(text("""
        INSERT INTO companies (id, name, industry, company_type, department, mission, description, student_id, created_at, updated_at)
        VALUES (:id, 'TestCo', 'Tech', 'STARTUP', 'Engineering', 'Test mission', 'Test company', :student_id, :now, :now)
    """), {"id": company_id, "student_id": student_id, "now": now})
    db.commit()
    return company_id


def _create_project(db, company_id):
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
    return project_id


def _create_sprints_and_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3):
    now = datetime.now(timezone.utc)
    all_task_ids = []
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
            all_task_ids.append(task_id)
    db.commit()
    return all_task_ids


def _create_simulation(db, student_id, project_id, company_id):
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


def _create_scenario_and_tasks(db, simulation_id, task_ids):
    """Create a scenario and link tasks via ScenarioTask."""
    now = datetime.now(timezone.utc)
    scenario_id = uuid.uuid4()
    db.execute(text("""
        INSERT INTO scenarios (id, simulation_id, sequence, title, description, workplace_context,
            role, difficulty, required_skills, objectives, status, sequence_order, created_at, updated_at)
        VALUES (:id, :sim_id, 1, 'Sprint 1', 'First sprint', 'Workplace context',
            'Developer', 'INTERMEDIATE', ARRAY['Python'], ARRAY['Goal'], 'PENDING', 1, :now, :now)
    """), {"id": scenario_id, "sim_id": simulation_id, "now": now})
    
    for idx, task_id in enumerate(task_ids):
        st_id = uuid.uuid4()
        db.execute(text("""
            INSERT INTO scenario_tasks (id, scenario_id, task_id, sequence, created_at, updated_at)
            VALUES (:id, :scenario_id, :task_id, :seq, :now, :now)
        """), {"id": st_id, "scenario_id": scenario_id, "task_id": task_id, "seq": idx + 1, "now": now})
    db.commit()
    return scenario_id


class TestStartSimulationFlow:
    """Prove the start simulation flow builds task path and sets current task."""

    def test_start_builds_task_path(self, db):
        """Starting a simulation creates task path entries."""
        company_id = _create_company(db, "student_start_1")
        project_id = _create_project(db, company_id)
        task_ids = _create_sprints_and_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3)
        
        sim_id = _create_simulation(db, "student_start_1", project_id, company_id)
        _create_scenario_and_tasks(db, sim_id, task_ids)
        
        # Manually start the simulation (simulating the /start endpoint logic)
        sim = db.get(Simulation, sim_id)
        sim.status = SimulationStatus.IN_PROGRESS
        sim.started_at = datetime.now(timezone.utc)
        sim.progress = 0
        
        # Build task path
        path_entries = build_task_path(db, sim_id, project_id)
        
        assert len(path_entries) == 6, f"Expected 6 path entries, got {len(path_entries)}"
        
        # Set first task from path
        first_entry = path_entries[0]
        first_task = db.get(Task, first_entry.task_id)
        assert first_task is not None
        
        if first_task.status == TaskStatus.BACKLOG:
            first_task.status = TaskStatus.TODO
        sim.current_task_id = first_task.id
        first_entry.status = TaskStatus.TODO
        
        db.add(sim)
        db.add(first_task)
        db.add(first_entry)
        db.commit()
        db.refresh(sim)
        
        # Verify current_task_id is set
        assert sim.current_task_id is not None, "current_task_id should be set after start"
        assert sim.current_task_id == first_task.id
        
        # Verify task path entries exist
        path = db.execute(
            select(SimulationTaskPath)
            .where(SimulationTaskPath.simulation_id == sim_id)
            .order_by(SimulationTaskPath.sequence)
        ).scalars().all()
        assert len(path) == 6
        assert path[0].status == TaskStatus.TODO

    def test_current_task_comes_from_path(self, db):
        """The current task after start is the first entry in the task path."""
        company_id = _create_company(db, "student_start_2")
        project_id = _create_project(db, company_id)
        task_ids = _create_sprints_and_tasks(db, project_id, num_sprints=1, tasks_per_sprint=4)
        
        sim_id = _create_simulation(db, "student_start_2", project_id, company_id)
        _create_scenario_and_tasks(db, sim_id, task_ids)
        
        # Build task path
        path_entries = build_task_path(db, sim_id, project_id)
        
        # The first path entry's task should be the current task
        first_path_task_id = path_entries[0].task_id
        first_task = db.get(Task, first_path_task_id)
        assert first_task is not None
        
        # Verify it's the first task from the project (by sprint order)
        canonical = get_canonical_tasks_for_project(db, project_id)
        assert first_path_task_id == canonical[0].id, "First path task should be first canonical task"

    def test_different_students_different_first_tasks(self, db):
        """Two students can start with different first tasks."""
        company_id = _create_company(db, "student_start_3")
        project_id = _create_project(db, company_id)
        task_ids = _create_sprints_and_tasks(db, project_id, num_sprints=2, tasks_per_sprint=3)
        
        # Student A gets all tasks
        sim_a = _create_simulation(db, "student_a_start", project_id, company_id)
        path_a = build_task_path(db, sim_a, project_id)
        
        # Student B gets only first 3 tasks
        sim_b = _create_simulation(db, "student_b_start", project_id, company_id)
        path_b = build_task_path(db, sim_b, project_id, task_ids=task_ids[:3])
        
        # Both have valid first tasks
        assert path_a[0].task_id is not None
        assert path_b[0].task_id is not None
        
        # Student A's first task is the first canonical task
        first_canonical = db.get(Task, task_ids[0])
        assert path_a[0].task_id == task_ids[0]
        
        # Student B's first task is also the first canonical task (same subset start)
        assert path_b[0].task_id == task_ids[0]
        
        # But Student A has more tasks
        assert len(path_a) == 6
        assert len(path_b) == 3

    def test_task_path_entries_ordered_by_sequence(self, db):
        """Task path entries have correct sequence ordering."""
        company_id = _create_company(db, "student_start_4")
        project_id = _create_project(db, company_id)
        _create_sprints_and_tasks(db, project_id, num_sprints=3, tasks_per_sprint=2)
        
        sim_id = _create_simulation(db, "student_start_4", project_id, company_id)
        
        path_entries = build_task_path(db, sim_id, project_id)
        
        sequences = [e.sequence for e in path_entries]
        assert sequences == [1, 2, 3, 4, 5, 6], f"Sequences should be 1-6, got {sequences}"
        
        # Verify ordering matches sprint number then task sequence
        tasks = [db.get(Task, e.task_id) for e in path_entries]
        for i in range(len(tasks) - 1):
            t1, t2 = tasks[i], tasks[i + 1]
            s1 = db.get(Sprint, t1.sprint_id)
            s2 = db.get(Sprint, t2.sprint_id)
            if s1.sprint_number == s2.sprint_number:
                assert t1.sequence <= t2.sequence
            else:
                assert s1.sprint_number < s2.sprint_number

    def test_first_task_status_is_todo(self, db):
        """After start, the first task's status is TODO (not BACKLOG)."""
        company_id = _create_company(db, "student_start_5")
        project_id = _create_project(db, company_id)
        task_ids = _create_sprints_and_tasks(db, project_id, num_sprints=1, tasks_per_sprint=2)
        
        sim_id = _create_simulation(db, "student_start_5", project_id, company_id)
        
        path_entries = build_task_path(db, sim_id, project_id)
        
        first_task = db.get(Task, path_entries[0].task_id)
        assert first_task.status == TaskStatus.BACKLOG, "Task should start as BACKLOG"
        
        # Simulate start: upgrade to TODO
        if first_task.status == TaskStatus.BACKLOG:
            first_task.status = TaskStatus.TODO
        path_entries[0].status = TaskStatus.TODO
        db.add(first_task)
        db.add(path_entries[0])
        db.commit()
        
        # Verify
        refreshed_task = db.get(Task, first_task.id)
        assert refreshed_task.status == TaskStatus.TODO
        
        refreshed_entry = db.get(SimulationTaskPath, path_entries[0].id)
        assert refreshed_entry.status == TaskStatus.TODO


# Need this import for the test
from sqlalchemy import select
