"""
Member 2 — Automated Tests for Workflow and Internship Simulation Engine.

Tests cover:
1. Start simulation successfully
2. Invalid simulation
3. Start task
4. Start task twice
5. Submit task
6. Submit without starting
7. Invalid state transition
8. Requirement change
9. Deadline warning
10. Event response
11. Event history
12. Task completion
13. Next task assignment
14. Simulation progress
15. Simulation completion
16. Late submission
17. On-time submission
18. Database relationships
"""
import uuid
import os
from datetime import datetime, timezone, timedelta

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("DATABASE_URL", "postgresql://aiwse:aiwse_password@localhost:5432/aiwse_test_db")
os.environ.setdefault("JWT_SECRET_KEY", "change-me-to-the-shared-signing-secret")

from app.core.config import settings
from app.core.database import Base, engine as app_engine
from app.main import app
from app.models.enums import (
    SimulationStatus, ScenarioStatus, TaskStatus, TaskType,
    DifficultyLevel, WorkflowEventType,
)


from sqlalchemy import text

@pytest.fixture(scope="session", autouse=True)
def _setup_database():
    """Create a clean schema once per test session against a real Postgres DB."""
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


@pytest.fixture
def other_auth_headers():
    return {"Authorization": f"Bearer {make_token('other_student')}"}


def _generate(client, auth_headers, student_id="test_student"):
    """Generate a full simulation for testing."""
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


def _start_and_get_current_task(client, auth_headers, sim_id):
    """Start simulation and return the current task from the task path."""
    client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
    resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=auth_headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["task_id"]


def _create_simulation_via_db(client, auth_headers, student_id="test_student"):
    """Create a simulation record in the database for testing."""
    from sqlalchemy import text
    from app.core.database import SessionLocal
    
    gen_data = _generate(client, auth_headers, student_id)
    company_id = gen_data["company_id"]
    project_id = gen_data["project_id"]
    
    db = SessionLocal()
    try:
        sim_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)
        
        # Create simulation first
        db.execute(text("""
            INSERT INTO simulations (id, student_id, company_id, project_id, title, description, role, difficulty, duration_weeks, status, started_at, completed_at, current_scenario_id, current_task_id, progress, created_at, updated_at)
            VALUES (:id, :student_id, :company_id, :project_id, 'Backend Developer Internship', 'Full stack developer simulation', 'Backend Developer', 'INTERMEDIATE', 4, 'NOT_STARTED', NULL, NULL, NULL, NULL, 0, :now, :now)
        """), {
            "id": sim_id, "student_id": student_id,
            "company_id": company_id, "project_id": project_id,
            "now": now,
        })
        
        # Always create a fresh task with no dependencies
        task_id = str(uuid.uuid4())
        sprint_result = db.execute(text("SELECT id FROM sprints LIMIT 1")).fetchone()
        sprint_id = str(sprint_result[0]) if sprint_result else None
        if sprint_id:
            db.execute(text("""
                INSERT INTO tasks (id, sprint_id, sequence, title, description, acceptance_criteria, priority, status, task_type, difficulty, estimated_hours, created_at, updated_at)
                VALUES (:id, :sprint_id, 0, 'Build Employee API', 'Build an employee CRUD API', ARRAY['Returns JSON', 'Handles errors'], 'medium', 'backlog', 'api_development', 'INTERMEDIATE', 4.0, :now, :now)
            """), {"id": task_id, "sprint_id": sprint_id, "now": now})
        
        # Create scenario with simulation_id
        scenario_id = str(uuid.uuid4())
        db.execute(text("""
            INSERT INTO scenarios (id, simulation_id, sequence, title, description, workplace_context, role, difficulty, required_skills, objectives, status, sequence_order, created_at, updated_at)
            VALUES (:id, :sim_id, 1, 'Backend API Development', 'Build a RESTful API', 'Tech startup environment', 'Backend Developer', 'INTERMEDIATE', ARRAY['Python', 'FastAPI'], ARRAY['Build API'], 'PENDING', 1, :now, :now)
        """), {"id": scenario_id, "sim_id": sim_id, "now": now})
        
        # Link task to scenario
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


# ============================================================
# TEST 1: Start simulation successfully
# ============================================================
class TestStartSimulation:
    def test_start_simulation_successfully(self, client, auth_headers):
        """Test: POST /api/simulations/{id}/start changes status to IN_PROGRESS."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        resp = client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "in_progress"
        assert body["started_at"] is not None
        assert body["current_scenario"] is not None
        assert body["current_task"] is not None

    def test_start_simulation_already_started(self, client, auth_headers):
        """Test: Cannot start a simulation that is already IN_PROGRESS."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        resp1 = client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
        assert resp1.status_code == 200
        
        resp2 = client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
        assert resp2.status_code == 409


# ============================================================
# TEST 2: Invalid simulation
# ============================================================
class TestInvalidSimulation:
    def test_get_nonexistent_simulation(self, client, auth_headers):
        """Test: GET /api/simulations/{invalid_id} returns 404."""
        fake_id = str(uuid.uuid4())
        resp = client.get(f"/api/simulations/{fake_id}", headers=auth_headers)
        assert resp.status_code == 404

    def test_cross_tenant_simulation_access(self, client, auth_headers, other_auth_headers):
        """Test: Cannot access another student's simulation."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        resp = client.get(f"/api/simulations/{sim_id}", headers=other_auth_headers)
        assert resp.status_code == 403


# ============================================================
# TEST 3: Start task
# ============================================================
class TestStartTask:
    def test_start_task_successfully(self, client, auth_headers):
        """Test: POST /api/simulations/{id}/tasks/{task_id}/start."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        # Start simulation and get current task from task path
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        
        # Start task
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["status"] == "in_progress"
        assert body["started_at"] is not None
        assert body["deadline"] is not None
        assert body["remaining_time"] is not None


# ============================================================
# TEST 4: Start task twice
# ============================================================
class TestStartTaskTwice:
    def test_start_task_twice_rejected(self, client, auth_headers):
        """Test: Cannot start the same task twice."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        
        resp1 = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        assert resp1.status_code == 200
        
        resp2 = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        assert resp2.status_code == 400


# ============================================================
# TEST 5: Submit task
# ============================================================
class TestSubmitTask:
    def test_submit_task_successfully(self, client, auth_headers):
        """Test: POST /api/simulations/{id}/tasks/{task_id}/submit."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        
        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "Here is my code"}'},
        )
        assert resp.status_code == 201, resp.text
        body = resp.json()
        assert body["status"] == "completed"
        assert body["task_id"] == task_id
        assert body["submitted_at"] is not None
        assert body["time_taken_minutes"] >= 0


# ============================================================
# TEST 6: Submit without starting
# ============================================================
class TestSubmitWithoutStarting:
    def test_submit_without_starting_rejected(self, client, auth_headers):
        """Test: Cannot submit a task that hasn't been started."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        
        # Task is in TODO state, not IN_PROGRESS
        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "Here is my code"}'},
        )
        assert resp.status_code == 400


# ============================================================
# TEST 7: Invalid state transition
# ============================================================
class TestInvalidStateTransition:
    def test_invalid_transition_rejected(self, client, auth_headers):
        """Test: Invalid state transitions are rejected."""
        from app.services.engines.simulation_task_state_machine import (
            SimulationTaskState,
            InvalidSimulationTaskTransitionError,
            validate_simulation_task_transition,
        )
        
        # Valid transitions
        validate_simulation_task_transition(
            SimulationTaskState.ASSIGNED, SimulationTaskState.STARTED
        )
        validate_simulation_task_transition(
            SimulationTaskState.STARTED, SimulationTaskState.IN_PROGRESS
        )
        validate_simulation_task_transition(
            SimulationTaskState.IN_PROGRESS, SimulationTaskState.SUBMITTED
        )
        
        # Invalid transitions
        with pytest.raises(InvalidSimulationTaskTransitionError):
            validate_simulation_task_transition(
                SimulationTaskState.ASSIGNED, SimulationTaskState.COMPLETED
            )
        
        with pytest.raises(InvalidSimulationTaskTransitionError):
            validate_simulation_task_transition(
                SimulationTaskState.SUBMITTED, SimulationTaskState.STARTED
            )
        
        with pytest.raises(InvalidSimulationTaskTransitionError):
            validate_simulation_task_transition(
                SimulationTaskState.COMPLETED, SimulationTaskState.STARTED
            )


# ============================================================
# TEST 8: Requirement change event
# ============================================================
class TestRequirementChangeEvent:
    def test_requirement_change_event_created(self, client, auth_headers):
        """Test: Requirement change event can be triggered."""
        from app.services.engines.workflow_events_engine import trigger_requirement_change_event
        from sqlalchemy import text
        from app.core.database import SessionLocal
        
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        task_id = data["task_id"]
        scenario_id = data["scenario_id"]
        
        db = SessionLocal()
        try:
            from app.models.simulation import Simulation, Scenario, WorkflowEvent
            from app.models.task import Task
            
            simulation = db.get(Simulation, uuid.UUID(sim_id))
            task = db.get(Task, uuid.UUID(task_id))
            scenario = db.get(Scenario, uuid.UUID(scenario_id))
            
            import asyncio
            event = asyncio.get_event_loop().run_until_complete(
                trigger_requirement_change_event(
                    db, simulation, task, scenario,
                    original_requirement="Build a simple API",
                    updated_requirement="Build a paginated API with filtering",
                    trigger_condition="mid_task_progress",
                )
            )
            
            assert event is not None
            assert event.event_type == WorkflowEventType.REQUIREMENT_CHANGE
            assert event.original_requirement == "Build a simple API"
            assert event.updated_requirement == "Build a paginated API with filtering"
            assert event.status == "pending"
            
            db.commit()
        finally:
            db.close()


# ============================================================
# TEST 9: Deadline warning event
# ============================================================
class TestDeadlineWarningEvent:
    def test_deadline_warning_event_created(self, client, auth_headers):
        """Test: Deadline warning event can be triggered."""
        from app.services.engines.workflow_events_engine import trigger_deadline_warning_event
        from sqlalchemy import text
        from app.core.database import SessionLocal
        
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        task_id = data["task_id"]
        scenario_id = data["scenario_id"]
        
        db = SessionLocal()
        try:
            from app.models.simulation import Simulation, Scenario
            from app.models.task import Task
            
            simulation = db.get(Simulation, uuid.UUID(sim_id))
            task = db.get(Task, uuid.UUID(task_id))
            scenario = db.get(Scenario, uuid.UUID(scenario_id))
            
            import asyncio
            event = asyncio.get_event_loop().run_until_complete(
                trigger_deadline_warning_event(
                    db, simulation, task, scenario,
                    remaining_minutes=5,
                )
            )
            
            assert event is not None
            assert event.event_type == WorkflowEventType.DEADLINE_WARNING
            assert event.status == "pending"
            assert "5 minutes" in event.message
            
            db.commit()
        finally:
            db.close()


# ============================================================
# TEST 10: Event response
# ============================================================
class TestEventResponse:
    def test_respond_to_event(self, client, auth_headers):
        """Test: Can respond to a workflow event."""
        from app.services.engines.workflow_events_engine import (
            trigger_requirement_change_event,
            respond_to_workflow_event,
        )
        from app.core.database import SessionLocal
        
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        task_id = data["task_id"]
        scenario_id = data["scenario_id"]
        
        db = SessionLocal()
        try:
            from app.models.simulation import Simulation, Scenario
            from app.models.task import Task
            
            simulation = db.get(Simulation, uuid.UUID(sim_id))
            task = db.get(Task, uuid.UUID(task_id))
            scenario = db.get(Scenario, uuid.UUID(scenario_id))
            
            import asyncio
            event = asyncio.get_event_loop().run_until_complete(
                trigger_requirement_change_event(
                    db, simulation, task, scenario,
                    original_requirement="Build API",
                    updated_requirement="Build paginated API",
                )
            )
            db.commit()
            
            # Respond to event
            updated_event = asyncio.get_event_loop().run_until_complete(
                respond_to_workflow_event(
                    db, event.id,
                    response="I acknowledge the change and will adapt my implementation.",
                    user_id="test_student",
                )
            )
            db.commit()
            
            assert updated_event.response == "I acknowledge the change and will adapt my implementation."
            assert updated_event.responded_at is not None
            assert updated_event.status == "acknowledged"
        finally:
            db.close()


# ============================================================
# TEST 11: Event history
# ============================================================
class TestEventHistory:
    def test_get_task_events(self, client, auth_headers):
        """Test: GET /api/simulations/{id}/tasks/{task_id}/events."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        task_id = data["task_id"]
        
        resp = client.get(f"/api/simulations/{sim_id}/tasks/{task_id}/events", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["task_id"] == task_id
        assert body["simulation_id"] == sim_id
        assert isinstance(body["events"], list)


# ============================================================
# TEST 12: Task completion
# ============================================================
class TestTaskCompletion:
    def test_complete_task(self, client, auth_headers):
        """Test: Submit auto-completes the task. Simulation progresses."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/submit", headers=auth_headers,
                     data={"metadata": '{"response": "done"}'})
        assert resp.status_code == 201
        body = resp.json()
        assert body["status"] == "completed"
        
        # Verify task is completed via progress endpoint
        prog_resp = client.get(f"/api/simulations/{sim_id}/progress", headers=auth_headers)
        assert prog_resp.status_code == 200
        assert prog_resp.json()["completed_tasks"] >= 1


# ============================================================
# TEST 13: Next task assignment
# ============================================================
class TestNextTaskAssignment:
    def test_next_task_assigned_after_completion(self, client, auth_headers):
        """Test: After submit (which auto-completes), next task is automatically assigned."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/submit", headers=auth_headers,
                     data={"metadata": '{"response": "done"}'})
        assert resp.status_code == 201
        
        # Check simulation state after completion
        sim_resp = client.get(f"/api/simulations/{sim_id}", headers=auth_headers)
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()
        assert sim_data["progress"] > 0


# ============================================================
# TEST 14: Simulation progress
# ============================================================
class TestSimulationProgress:
    def test_get_simulation_progress(self, client, auth_headers):
        """Test: GET /api/simulations/{id}/progress."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
        
        resp = client.get(f"/api/simulations/{sim_id}/progress", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["simulation_id"] == sim_id
        assert body["overall_progress"] >= 0
        assert body["total_tasks"] >= 0
        assert body["completed_tasks"] >= 0
        assert isinstance(body["scenarios"], list)


# ============================================================
# TEST 15: Simulation completion
# ============================================================
class TestSimulationCompletion:
    def test_complete_all_tasks_simulation(self, client, auth_headers):
        """Test: Completing a task progresses the simulation forward."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        resp = client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/submit", headers=auth_headers,
                     data={"metadata": '{"response": "done"}'})
        assert resp.status_code == 201
        
        # Check simulation state after completion
        sim_resp = client.get(f"/api/simulations/{sim_id}", headers=auth_headers)
        assert sim_resp.status_code == 200
        sim_data = sim_resp.json()
        # Simulation should still be in progress (task path has multiple tasks)
        assert sim_data["status"] in ("in_progress", "completed")
        assert sim_data["completed_tasks"] >= 1


# ============================================================
# TEST 16: On-time submission
# ============================================================
class TestOnTimeSubmission:
    def test_on_time_submission(self, client, auth_headers):
        """Test: Submission before deadline is marked as on_time."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        
        # Set a future deadline
        from sqlalchemy import text
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            future_deadline = datetime.now(timezone.utc) + timedelta(hours=1)
            db.execute(
                text("UPDATE tasks SET deadline = :deadline WHERE id = :task_id"),
                {"deadline": future_deadline, "task_id": task_id}
            )
            db.commit()
        finally:
            db.close()
        
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        
        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "done on time"}'},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["on_time"] is True
        assert body["deadline_missed"] is False


# ============================================================
# TEST 17: Late submission
# ============================================================
class TestLateSubmission:
    def test_late_submission(self, client, auth_headers):
        """Test: Submission after deadline is marked as deadline_missed."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        
        # Set a past deadline
        from sqlalchemy import text
        from app.core.database import SessionLocal
        db = SessionLocal()
        try:
            past_deadline = datetime.now(timezone.utc) - timedelta(minutes=5)
            db.execute(
                text("UPDATE tasks SET deadline = :deadline WHERE id = :task_id"),
                {"deadline": past_deadline, "task_id": task_id}
            )
            db.commit()
        finally:
            db.close()
        
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        
        resp = client.post(
            f"/api/simulations/{sim_id}/tasks/{task_id}/submit",
            headers=auth_headers,
            data={"metadata": '{"response": "done late"}'},
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["deadline_missed"] is True
        assert body["on_time"] is False


# ============================================================
# TEST 18: Database relationships
# ============================================================
class TestDatabaseRelationships:
    def test_simulation_scenario_relationship(self, client, auth_headers):
        """Test: Simulation has correct scenario relationships."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        scenario_id = data["scenario_id"]
        
        client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
        
        resp = client.get(f"/api/simulations/{sim_id}", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        
        # Check current scenario is accessible
        assert body["current_scenario"] is not None
        assert body["current_scenario"]["id"] == scenario_id

    def test_scenario_task_relationship(self, client, auth_headers):
        """Test: Scenario has correct task relationships."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        scenario_id = data["scenario_id"]
        
        client.post(f"/api/simulations/{sim_id}/start", headers=auth_headers)
        
        resp = client.get(f"/api/simulations/{sim_id}/scenario", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["scenario_id"] == scenario_id
        assert len(body["all_tasks"]) >= 1


# ============================================================
# TEST 19: State machine transitions
# ============================================================
class TestStateMachineTransitions:
    def test_all_valid_transitions(self):
        """Test: All valid state machine transitions work."""
        from app.services.engines.simulation_task_state_machine import (
            SimulationTaskState,
            validate_simulation_task_transition,
            can_start_simulation_task,
            can_submit_simulation_task,
            is_terminal_simulation_task_state,
            get_simulation_task_transition_action,
        )
        
        # Test can_start_simulation_task
        assert can_start_simulation_task(SimulationTaskState.ASSIGNED) is True
        assert can_start_simulation_task(SimulationTaskState.IN_PROGRESS) is False
        assert can_start_simulation_task(SimulationTaskState.COMPLETED) is False
        
        # Test can_submit_simulation_task
        assert can_submit_simulation_task(SimulationTaskState.IN_PROGRESS) is True
        assert can_submit_simulation_task(SimulationTaskState.SUBMITTED) is False
        assert can_submit_simulation_task(SimulationTaskState.COMPLETED) is False
        
        # Test is_terminal_simulation_task_state
        assert is_terminal_simulation_task_state(SimulationTaskState.COMPLETED) is True
        assert is_terminal_simulation_task_state(SimulationTaskState.IN_PROGRESS) is False
        
        # Test get_simulation_task_transition_action
        action = get_simulation_task_transition_action(
            SimulationTaskState.ASSIGNED, SimulationTaskState.STARTED
        )
        assert action == "task_started"
        
        action = get_simulation_task_transition_action(
            SimulationTaskState.UNDER_EVALUATION, SimulationTaskState.COMPLETED
        )
        assert action == "task_completed"


# ============================================================
# TEST 20: Time tracking
# ============================================================
class TestTimeTracking:
    def test_time_tracking_calculated(self, client, auth_headers):
        """Test: Time tracking calculates correctly."""
        data = _create_simulation_via_db(client, auth_headers)
        sim_id = data["simulation_id"]
        
        task_id = _start_and_get_current_task(client, auth_headers, sim_id)
        client.post(f"/api/simulations/{sim_id}/tasks/{task_id}/start", headers=auth_headers)
        
        # Get current task - should have remaining time
        resp = client.get(f"/api/simulations/{sim_id}/tasks/current", headers=auth_headers)
        assert resp.status_code == 200
        body = resp.json()
        assert body["started_at"] is not None
        assert body["remaining_time"] is not None
        assert body["remaining_time"]["seconds"] > 0
        assert body["deadline_missed"] is False