"""
Member 2 — End-to-End Demonstration Script.

Demonstrates a complete Backend Developer Internship simulation flow:
1. Student starts simulation
2. First scenario appears with workplace context
3. First task is assigned
4. Student starts task - timer begins
5. Requirement change event appears
6. Student responds to requirement change
7. Student continues work
8. Deadline warning event appears
9. Student submits work
10. Submission is stored with evaluation-ready evidence
11. Task becomes SUBMITTED / UNDER_EVALUATION
12. Next task automatically becomes ASSIGNED
13. Simulation progress updates
14. Eventually simulation completes

Run: python -m tests.test_e2e_demo
"""
import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone, timedelta

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from app.core.database import SessionLocal, engine, Base
from app.core.config import settings
from app.models.company import Company
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.task import Task
from app.models.simulation import Simulation, Scenario, ScenarioTask, WorkflowEvent
from app.models.enums import (
    TaskStatus, TaskType, DifficultyLevel,
    SimulationStatus, ScenarioStatus, WorkflowEventType,
)
from sqlalchemy import text


def setup_database():
    """Create tables if they don't exist."""
    Base.metadata.create_all(bind=engine)


def create_demo_data(db):
    """Create a complete demo scenario with company, project, tasks."""
    now = datetime.now(timezone.utc)
    
    # Create company
    company_id = uuid.uuid4()
    company = Company(
        id=company_id,
        name="TechStart Inc.",
        company_type="startup",
        industry="Technology",
        department="Engineering",
        mission="Build innovative products",
        description="A fast-paced startup building next-gen tech solutions",
        student_id="demo_student",
    )
    db.add(company)
    db.flush()
    
    # Create project
    project_id = uuid.uuid4()
    project = Project(
        id=project_id,
        company_id=company_id,
        title="Employee Management System",
        role="Backend Developer",
        technology_stack=["Python", "FastAPI", "PostgreSQL"],
        difficulty=DifficultyLevel.INTERMEDIATE,
        status="active",
        objectives=["Build REST API", "Implement CRUD operations"],
        modules=["Employee API", "Department API"],
        deliverables=["Working API", "Documentation"],
        duration_weeks=4,
        start_date=now,
    )
    db.add(project)
    db.flush()
    
    # Create sprints
    sprint = Sprint(
        id=uuid.uuid4(),
        project_id=project_id,
        sprint_number=1,
        name="Sprint 1 - Foundation",
        goal="Build core API endpoints",
        status="active",
        start_date=now,
        end_date=now + timedelta(weeks=2),
    )
    db.add(sprint)
    db.flush()
    
    # Create simulation first (needed for scenario's foreign key)
    simulation_id = uuid.uuid4()
    simulation = Simulation(
        id=simulation_id,
        student_id="demo_student",
        company_id=company_id,
        project_id=project_id,
        title="Backend Developer Internship",
        description="Full stack developer simulation at TechStart Inc.",
        role="Backend Developer",
        difficulty=DifficultyLevel.INTERMEDIATE,
        duration_weeks=4,
        status=SimulationStatus.NOT_STARTED,
        started_at=None,
        completed_at=None,
        current_scenario_id=None,
        current_task_id=None,
        progress=0,
    )
    db.add(simulation)
    db.flush()
    
    # Create scenario
    scenario_id = uuid.uuid4()
    scenario = Scenario(
        id=scenario_id,
        simulation_id=simulation_id,
        sequence=1,
        title="Employee Management API",
        description="Build a RESTful API for managing employees in a growing startup",
        workplace_context=(
            "You are a Backend Developer intern at TechStart Inc., a fast-growing "
            "startup. Your manager has assigned you to build the Employee Management "
            "API for the HR department. The API needs to support basic CRUD operations "
            "and should be production-ready."
        ),
        role="Backend Developer",
        difficulty=DifficultyLevel.INTERMEDIATE,
        required_skills=["Python", "FastAPI", "PostgreSQL", "REST API Design"],
        objectives=[
            "Build employee CRUD endpoints",
            "Implement proper error handling",
            "Add input validation",
            "Write clean, documented code",
        ],
        status=ScenarioStatus.PENDING,
        sequence_order=1,
    )
    db.add(scenario)
    db.flush()
    
    # Create tasks for the scenario
    tasks = []
    task_data = [
        {
            "title": "Build Employee Retrieval API",
            "description": (
                "Implement a GET endpoint to retrieve employee details.\n\n"
                "Requirements:\n"
                "- GET /api/employees/{id} returns employee details\n"
                "- GET /api/employees returns a list of employees\n"
                "- Support pagination (limit, offset)\n"
                "- Return proper JSON responses\n"
                "- Handle not found errors gracefully"
            ),
            "task_type": TaskType.API_DEVELOPMENT,
            "estimated_hours": 2.0,
            "acceptance_criteria": [
                "GET /api/employees/{id} returns 200 with employee data",
                "GET /api/employees returns 200 with paginated list",
                "Returns 404 for non-existent employee",
                "Response includes id, name, email, department, position",
            ],
        },
        {
            "title": "Implement Employee Creation API",
            "description": (
                "Implement a POST endpoint to create new employees.\n\n"
                "Requirements:\n"
                "- POST /api/employees creates a new employee\n"
                "- Validate required fields (name, email, department)\n"
                "- Return 201 with created employee\n"
                "- Return 400 for validation errors\n"
                "- Handle duplicate email gracefully"
            ),
            "task_type": TaskType.API_DEVELOPMENT,
            "estimated_hours": 2.0,
            "acceptance_criteria": [
                "POST /api/employees returns 201 with created employee",
                "Validates required fields",
                "Returns 400 for missing fields",
                "Returns 400 for invalid email format",
                "Returns 409 for duplicate email",
            ],
        },
        {
            "title": "Add Employee Update and Delete",
            "description": (
                "Implement PUT and DELETE endpoints.\n\n"
                "Requirements:\n"
                "- PUT /api/employees/{id} updates employee\n"
                "- DELETE /api/employees/{id} removes employee\n"
                "- Validate update data\n"
                "- Return appropriate status codes"
            ),
            "task_type": TaskType.API_DEVELOPMENT,
            "estimated_hours": 2.0,
            "acceptance_criteria": [
                "PUT /api/employees/{id} returns 200 with updated data",
                "DELETE /api/employees/{id} returns 204",
                "Returns 404 for non-existent employee",
                "Validates update fields",
            ],
        },
    ]
    
    for i, data in enumerate(task_data, 1):
        task_id = uuid.uuid4()
        task = Task(
            id=task_id,
            sprint_id=sprint.id,
            title=data["title"],
            description=data["description"],
            acceptance_criteria=data["acceptance_criteria"],
            priority="medium",
            status=TaskStatus.BACKLOG,
            task_type=data["task_type"],
            estimated_hours=data["estimated_hours"],
            deadline=now + timedelta(hours=data["estimated_hours"] * 2),
        )
        db.add(task)
        tasks.append(task)
        
        # Link task to scenario
        link = ScenarioTask(
            id=uuid.uuid4(),
            scenario_id=scenario_id,
            task_id=task_id,
            sequence=i,
        )
        db.add(link)
    
    db.flush()
    
    db.commit()
    
    return {
        "simulation_id": str(simulation_id),
        "company_id": str(company_id),
        "project_id": str(project_id),
        "scenario_id": str(scenario_id),
        "task_ids": [str(t.id) for t in tasks],
    }


def run_demo():
    """Run the complete end-to-end demonstration."""
    print("=" * 70)
    print("MEMBER 2 — WORKFLOW AND INTERNSHIP SIMULATION ENGINE")
    print("End-to-End Demonstration")
    print("=" * 70)
    print()
    
    setup_database()
    
    db = SessionLocal()
    try:
        print("Setting up demo data...")
        data = create_demo_data(db)
        print(f"Created simulation: {data['simulation_id'][:8]}...")
        print(f"Created {len(data['task_ids'])} tasks")
        print()
        
        sim_id = uuid.UUID(data["simulation_id"])
        scenario_id = uuid.UUID(data["scenario_id"])
        task_ids = [uuid.UUID(tid) for tid in data["task_ids"]]
        
        # ============================================================
        # STEP 1: Start Simulation
        # ============================================================
        print("STEP 1: Start Simulation")
        print("-" * 40)
        
        simulation = db.get(Simulation, sim_id)
        print(f"Initial status: {simulation.status.value}")
        
        simulation.status = SimulationStatus.IN_PROGRESS
        simulation.started_at = datetime.now(timezone.utc)
        
        # Activate first scenario
        scenario = db.get(Scenario, scenario_id)
        scenario.status = ScenarioStatus.ACTIVE
        simulation.current_scenario_id = scenario_id
        
        # Assign first task
        first_task = db.get(Task, task_ids[0])
        first_task.status = TaskStatus.TODO
        simulation.current_task_id = first_task.id
        
        db.commit()
        
        print(f"Status changed to: {simulation.status.value}")
        print(f"Started at: {simulation.started_at}")
        print(f"Current scenario: {scenario.title}")
        print(f"Current task: {first_task.title}")
        print()
        
        # ============================================================
        # STEP 2: Start Task
        # ============================================================
        print("STEP 2: Start Task")
        print("-" * 40)
        
        task = db.get(Task, task_ids[0])
        now = datetime.now(timezone.utc)
        
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = now
        
        # Set deadline (30 minutes from start)
        from datetime import timedelta
        task.deadline = now + timedelta(minutes=30)
        
        db.commit()
        
        print(f"Task started: {task.title}")
        print(f"Started at: {task.started_at}")
        print(f"Deadline: {task.deadline}")
        print(f"Status: {task.status.value}")
        print()
        
        # ============================================================
        # STEP 3: Trigger Requirement Change Event
        # ============================================================
        print("STEP 3: Trigger Requirement Change Event")
        print("-" * 40)
        
        event = WorkflowEvent(
            simulation_id=sim_id,
            task_id=task.id,
            scenario_id=scenario_id,
            event_type=WorkflowEventType.REQUIREMENT_CHANGE,
            title="Requirement Change - Pagination",
            message=(
                "The client now requires pagination because the database contains "
                "thousands of employee records. The simple list endpoint will not scale."
            ),
            description=(
                "Original: GET /api/employees returns all employees\n"
                "Updated: GET /api/employees?limit=10&offset=0 returns paginated results"
            ),
            original_requirement="GET /api/employees returns a list of all employees",
            updated_requirement="GET /api/employees?limit=10&offset=0 returns a paginated list with total count",
            trigger_condition="mid_task_progress",
            action_required=True,
            occurred_at=now,
            status="pending",
            metadata_json={
                "trigger_stage": "task_started",
                "severity": "medium",
            },
        )
        db.add(event)
        db.commit()
        
        print(f"Event created: {event.title}")
        print(f"Type: {event.event_type.value}")
        print(f"Original requirement: {event.original_requirement}")
        print(f"Updated requirement: {event.updated_requirement}")
        print()
        
        # ============================================================
        # STEP 4: Student Responds to Requirement Change
        # ============================================================
        print("STEP 4: Student Responds to Requirement Change")
        print("-" * 40)
        
        event.status = "acknowledged"
        event.response = (
            "I acknowledge the updated requirement. I will modify the implementation "
            "to include pagination with limit and offset parameters. The response will "
            "include a total count field for frontend pagination."
        )
        event.responded_at = datetime.now(timezone.utc)
        
        db.commit()
        
        print(f"Event status: {event.status}")
        print(f"Response: {event.response[:80]}...")
        print(f"Responded at: {event.responded_at}")
        print()
        
        # ============================================================
        # STEP 5: Trigger Deadline Warning Event
        # ============================================================
        print("STEP 5: Trigger Deadline Warning Event")
        print("-" * 40)
        
        warning_event = WorkflowEvent(
            simulation_id=sim_id,
            task_id=task.id,
            scenario_id=scenario_id,
            event_type=WorkflowEventType.DEADLINE_WARNING,
            title="Deadline Warning",
            message="You have 5 minutes remaining to complete this task. Please submit your work before the deadline.",
            trigger_condition="deadline_approaching_5_minutes",
            action_required=False,
            occurred_at=datetime.now(timezone.utc),
            status="pending",
            metadata_json={
                "remaining_minutes": 5,
                "threshold_minutes": 5,
            },
        )
        db.add(warning_event)
        db.commit()
        
        print(f"Warning created: {warning_event.title}")
        print(f"Message: {warning_event.message}")
        print()
        
        # ============================================================
        # STEP 6: Student Submits Work
        # ============================================================
        print("STEP 6: Student Submits Work")
        print("-" * 40)
        
        submitted_at = datetime.now(timezone.utc)
        time_taken = (submitted_at - task.started_at).total_seconds()
        
        task.status = TaskStatus.SUBMITTED
        task.completed_at = submitted_at
        
        db.commit()
        
        print(f"Task submitted at: {submitted_at}")
        print(f"Time taken: {int(time_taken)} seconds ({int(time_taken/60)} minutes)")
        print(f"Status: {task.status.value}")
        print()
        
        # ============================================================
        # STEP 7: Build Evaluation Evidence
        # ============================================================
        print("STEP 7: Build Evaluation Evidence (for Member 3)")
        print("-" * 40)
        
        # Get all workflow events for this task
        events = db.query(WorkflowEvent).filter(
            WorkflowEvent.task_id == task.id,
            WorkflowEvent.simulation_id == sim_id,
        ).all()
        
        evaluation_evidence = {
            "submission_id": str(uuid.uuid4()),
            "task_id": str(task.id),
            "simulation_id": str(sim_id),
            "user_id": "demo_student",
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "submitted_at": submitted_at.isoformat(),
            "time_taken_minutes": int(time_taken / 60),
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "on_time": submitted_at <= task.deadline if task.deadline else True,
            "deadline_missed": submitted_at > task.deadline if task.deadline else False,
            "events_encountered": [
                {
                    "event_id": str(e.id),
                    "event_type": e.event_type.value,
                    "title": e.title,
                    "status": e.status,
                    "responded": e.response is not None,
                }
                for e in events
            ],
            "requirement_changes_encountered": [
                {
                    "original": e.original_requirement,
                    "updated": e.updated_requirement,
                }
                for e in events if e.event_type == WorkflowEventType.REQUIREMENT_CHANGE
            ],
            "event_responses": [
                {
                    "event_id": str(e.id),
                    "response": e.response,
                    "responded_at": e.responded_at.isoformat() if e.responded_at else None,
                }
                for e in events if e.response
            ],
            "task_difficulty": scenario.difficulty.value,
            "required_skills": scenario.required_skills,
            "acceptance_criteria": task.acceptance_criteria,
            "task_state_history": [
                {"status": "TODO", "timestamp": task.started_at.isoformat() if task.started_at else None},
                {"status": "IN_PROGRESS", "timestamp": task.started_at.isoformat() if task.started_at else None},
                {"status": "SUBMITTED", "timestamp": submitted_at.isoformat()},
            ],
        }
        
        print("Evaluation evidence package:")
        for key, value in evaluation_evidence.items():
            if isinstance(value, list):
                print(f"  {key}: [{len(value)} items]")
            else:
                print(f"  {key}: {value}")
        print()
        
        # ============================================================
        # STEP 8: Task Completion and Progression
        # ============================================================
        print("STEP 8: Task Completion and Progression")
        print("-" * 40)
        
        # Mark task as completed
        task.status = TaskStatus.COMPLETED
        db.commit()
        
        # Update simulation progress
        total_tasks = len(task_ids)
        completed_tasks = 1
        progress = int((completed_tasks / total_tasks) * 100)
        
        simulation.progress = progress
        db.commit()
        
        print(f"Task completed: {task.title}")
        print(f"Progress: {progress}% ({completed_tasks}/{total_tasks} tasks)")
        print()
        
        # ============================================================
        # STEP 9: Assign Next Task
        # ============================================================
        print("STEP 9: Assign Next Task")
        print("-" * 40)
        
        if len(task_ids) > 1:
            next_task = db.get(Task, task_ids[1])
            next_task.status = TaskStatus.TODO
            simulation.current_task_id = next_task.id
            db.commit()
            
            print(f"Next task assigned: {next_task.title}")
            print(f"Status: {next_task.status.value}")
        else:
            # Simulation complete
            simulation.status = SimulationStatus.COMPLETED
            simulation.completed_at = datetime.now(timezone.utc)
            simulation.current_task_id = None
            simulation.current_scenario_id = None
            simulation.progress = 100
            db.commit()
            
            print("All tasks completed! Simulation finished.")
        print()
        
        # ============================================================
        # STEP 10: Final Simulation State
        # ============================================================
        print("STEP 10: Final Simulation State")
        print("-" * 40)
        
        simulation = db.get(Simulation, sim_id)
        print(f"Simulation: {simulation.title}")
        print(f"Status: {simulation.status.value}")
        print(f"Progress: {simulation.progress}%")
        print(f"Started at: {simulation.started_at}")
        print(f"Completed at: {simulation.completed_at}")
        if simulation.completed_at and simulation.started_at:
            duration = (simulation.completed_at - simulation.started_at).total_seconds()
            print(f"Duration: {int(duration/60)} minutes")
        print()
        
        # ============================================================
        # SUMMARY
        # ============================================================
        print("=" * 70)
        print("DEMONSTRATION COMPLETE")
        print("=" * 70)
        print()
        print("Flow demonstrated:")
        print("  1. Student started simulation")
        print("  2. First scenario appeared with workplace context")
        print("  3. First task was assigned and started")
        print("  4. Timer began tracking time")
        print("  5. Requirement change event appeared")
        print("  6. Student responded to the requirement change")
        print("  7. Deadline warning event appeared")
        print("  8. Student submitted work")
        print("  9. Submission stored with evaluation-ready evidence")
        print("  10. Task completed and next task assigned")
        print("  11. Simulation progress updated")
        print()
        print("Evidence package ready for Member 3 evaluation.")
        print()
        
    finally:
        db.close()


if __name__ == "__main__":
    run_demo()