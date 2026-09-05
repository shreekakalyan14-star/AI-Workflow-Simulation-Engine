import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, status, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.enums import SimulationStatus, ScenarioStatus, TaskStatus, WorkflowEventType
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.simulation import Simulation, Scenario, ScenarioTask, WorkflowEvent
from app.models.task import Task
from app.models.task_path import SimulationTaskPath
from app.models.submission import Submission, SubmissionVersion
from app.services.engines import trigger_workflow_event
from app.services.engines.simulation_task_state_machine import (
    SimulationTaskState,
    validate_simulation_task_transition,
    can_start_simulation_task,
    get_simulation_task_transition_action,
    get_project_status_for_simulation_state,
)
from app.services.submission.submission_service import SubmissionService
from app.services.file_storage import FileValidationError
from app.services.activity_log_service import log_activity

router = APIRouter(prefix="/api/simulations", tags=["Simulations"])


class CreateSimulationRequest(BaseModel):
    company_id: uuid.UUID
    project_id: uuid.UUID


class StartSimulationRequest(BaseModel):
    task_ids: Optional[List[uuid.UUID]] = None


@router.post("", status_code=status.HTTP_201_CREATED)
def create_simulation(
    body: CreateSimulationRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Create a new simulation for the given company and project."""
    company = db.get(Company, body.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your company")

    project = db.get(Project, body.project_id)
    if project is None or project.company_id != body.company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Check if a simulation already exists for this student + project
    existing = db.execute(
        select(Simulation).where(
            Simulation.student_id == user.student_id,
            Simulation.project_id == body.project_id,
        )
    ).scalar_one_or_none()
    if existing:
        return {
            "simulation_id": str(existing.id),
            "title": existing.title,
            "status": existing.status.value,
        }

    simulation = Simulation(
        student_id=user.student_id,
        company_id=body.company_id,
        project_id=body.project_id,
        title=f"{project.title} Simulation",
        description=f"Internship simulation for {project.title}",
        role=project.role,
        difficulty=project.difficulty,
        duration_weeks=project.duration_weeks,
        status=SimulationStatus.NOT_STARTED,
        progress=0,
    )
    db.add(simulation)
    db.flush()
    db.refresh(simulation)

    # Create scenarios from project sprints and link tasks
    from app.models.sprint import Sprint

    sprints = db.execute(
        select(Sprint)
        .where(Sprint.project_id == project.id)
        .order_by(Sprint.sprint_number)
    ).scalars().all()

    scenario_sequence = 1
    for sprint in sprints:
        # Get tasks for this sprint
        sprint_tasks = db.execute(
            select(Task)
            .where(Task.sprint_id == sprint.id)
            .order_by(Task.created_at)
        ).scalars().all()

        if not sprint_tasks:
            continue

        scenario = Scenario(
            simulation_id=simulation.id,
            sequence=scenario_sequence,
            title=sprint.name,
            description=sprint.goal,
            workplace_context=f"{project.title} - {sprint.name}",
            role=project.role,
            difficulty=project.difficulty,
            required_skills=project.technology_stack or [],
            objectives=[sprint.goal],
            status=ScenarioStatus.PENDING,
            sequence_order=scenario_sequence,
        )
        db.add(scenario)
        db.flush()

        for idx, task in enumerate(sprint_tasks):
            scenario_task = ScenarioTask(
                scenario_id=scenario.id,
                task_id=task.id,
                sequence=idx + 1,
            )
            db.add(scenario_task)

        scenario_sequence += 1

    db.flush()

    return {
        "simulation_id": str(simulation.id),
        "title": simulation.title,
        "description": simulation.description,
        "role": simulation.role,
        "difficulty": simulation.difficulty.value,
        "duration_weeks": simulation.duration_weeks,
        "status": simulation.status.value,
    }


def _get_owned_simulation(
    simulation_id: uuid.UUID,
    db: Session,
    user: CurrentUser,
) -> Simulation:
    simulation = db.get(Simulation, simulation_id)
    if simulation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Simulation not found")
    company = db.get(Company, simulation.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your simulation")
    return simulation


@router.get("/{simulation_id}")
def get_simulation(
    simulation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get simulation with current scenario, task, and progress information."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    current_scenario = None
    if simulation.current_scenario_id:
        current_scenario = db.get(Scenario, simulation.current_scenario_id)
    
    current_task = None
    if simulation.current_task_id:
        current_task = db.get(Task, simulation.current_task_id)
    
    # Count total and completed tasks
    total_tasks = 0
    completed_tasks = 0
    
    path_entries = db.execute(
        select(SimulationTaskPath).where(SimulationTaskPath.simulation_id == simulation.id)
    ).scalars().all()
    
    if path_entries:
        total_tasks = len(path_entries)
        completed_tasks = sum(1 for entry in path_entries if entry.task.status == TaskStatus.COMPLETED)
    elif simulation.scenarios:
        for scenario in simulation.scenarios:
            for scenario_task in scenario.tasks:
                total_tasks += 1
                if scenario_task.task.status == TaskStatus.COMPLETED:
                    completed_tasks += 1
    
    # Get active workflow event
    active_event = None
    if current_task:
        active_event = db.execute(
            select(WorkflowEvent)
            .where(
                WorkflowEvent.simulation_id == simulation_id,
                WorkflowEvent.task_id == current_task.id,
                WorkflowEvent.status.in_(["pending", "acknowledged"])
            )
            .order_by(WorkflowEvent.occurred_at.desc())
        ).scalar_one_or_none()
    
    # Calculate time remaining if task is in progress
    remaining_time = None
    if current_task and current_task.started_at and current_task.deadline:
        now = datetime.now(timezone.utc)
        if current_task.deadline > now:
            remaining_seconds = (current_task.deadline - now).total_seconds()
            remaining_time = {
                "seconds": int(remaining_seconds),
                "minutes": int(remaining_seconds / 60),
                "hours": int(remaining_seconds / 3600),
                "formatted": _format_remaining_time(remaining_seconds)
            }
        else:
            remaining_time = {
                "seconds": 0,
                "minutes": 0,
                "hours": 0,
                "formatted": "Expired",
                "deadline_missed": True
            }
    
    return {
        "simulation_id": str(simulation.id),
        "title": simulation.title,
        "description": simulation.description,
        "role": simulation.role,
        "difficulty": simulation.difficulty.value,
        "duration_weeks": simulation.duration_weeks,
        "status": simulation.status.value,
        "progress": simulation.progress,
        "started_at": simulation.started_at.isoformat() if simulation.started_at else None,
        "completed_at": simulation.completed_at.isoformat() if simulation.completed_at else None,
        "created_at": simulation.created_at.isoformat(),
        "current_scenario": {
            "id": str(current_scenario.id),
            "title": current_scenario.title,
            "description": current_scenario.description,
            "workplace_context": current_scenario.workplace_context,
            "role": current_scenario.role,
            "difficulty": current_scenario.difficulty.value,
            "required_skills": current_scenario.required_skills,
            "objectives": current_scenario.objectives,
            "status": current_scenario.status.value,
            "sequence": current_scenario.sequence,
        } if current_scenario else None,
        "current_task": {
            "id": str(current_task.id),
            "title": current_task.title,
            "description": current_task.description,
            "instructions": current_task.description,
            "difficulty": current_scenario.difficulty.value if current_scenario else "beginner",
            "task_type": current_task.task_type.value if current_task.task_type else "coding",
            "required_skills": current_scenario.required_skills if current_scenario else [],
            "expected_output": current_task.acceptance_criteria,
            "deadline": current_task.deadline.isoformat() if current_task.deadline else None,
            "status": current_task.status.value,
            "started_at": current_task.started_at.isoformat() if current_task.started_at else None,
            "remaining_time": remaining_time,
        } if current_task else None,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "progress_percentage": (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0,
        "active_workplace_event": {
            "id": str(active_event.id),
            "event_type": active_event.event_type.value,
            "title": active_event.title,
            "message": active_event.message,
            "description": active_event.description,
            "occurred_at": active_event.occurred_at.isoformat(),
            "status": active_event.status,
            "action_required": active_event.action_required,
            "original_requirement": active_event.original_requirement,
            "updated_requirement": active_event.updated_requirement,
        } if active_event else None,
    }


@router.post("/{simulation_id}/start", status_code=status.HTTP_200_OK)
async def start_simulation(
    simulation_id: uuid.UUID,
    body: StartSimulationRequest = StartSimulationRequest(),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Start a simulation: build task path, set first task, open workspace.

    Pass ``task_ids`` to give the student a personalised subset of canonical
    project tasks.  Omit to include every canonical task.
    """
    simulation = _get_owned_simulation(simulation_id, db, user)

    if simulation.status != SimulationStatus.NOT_STARTED:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Simulation already {simulation.status.value}. Cannot start again."
        )

    # Change status to IN_PROGRESS
    simulation.status = SimulationStatus.IN_PROGRESS
    simulation.started_at = datetime.now(timezone.utc)
    simulation.progress = 0

    # Build the student's personalised task path from canonical project tasks
    from app.services.simulation.task_path_builder import build_task_path
    path_entries = build_task_path(
        db, simulation_id, simulation.project_id, task_ids=body.task_ids
    )
    
    # Find the first scenario (by sequence) — lenient if missing
    first_scenario = db.execute(
        select(Scenario)
        .where(Scenario.simulation_id == simulation_id)
        .order_by(Scenario.sequence)
    ).scalars().first()
    
    if first_scenario:
        first_scenario.status = ScenarioStatus.ACTIVE
        simulation.current_scenario_id = first_scenario.id
        db.add(first_scenario)
    
    # Set current task from the first task path entry
    if path_entries:
        first_path_entry = path_entries[0]
        first_task = db.get(Task, first_path_entry.task_id)
        if first_task:
            if first_task.status == TaskStatus.BACKLOG:
                first_task.status = TaskStatus.TODO
            simulation.current_task_id = first_task.id
            first_path_entry.status = TaskStatus.TODO
            db.add(first_task)
            db.add(first_path_entry)
    
    db.add(simulation)
    db.flush()
    
    # Log activity
    from app.services.activity_log_service import log_activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor=user.student_id,
        action="simulation_started",
        detail=f"Started simulation '{simulation.title}'",
        simulation_id=str(simulation.id),
        scenario_id=str(first_scenario.id) if first_scenario else None,
        task_id=str(simulation.current_task_id) if simulation.current_task_id else None,
    )
    
    db.commit()
    db.refresh(simulation)
    
    # Return full simulation state
    return get_simulation(simulation_id, db, user)


@router.get("/{simulation_id}/progress")
def get_simulation_progress(
    simulation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get detailed progress information for a simulation."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    # Calculate progress by scenario
    scenario_progress = []
    total_tasks = 0
    completed_tasks = 0
    
    # Prefer task path (student-specific subset) when available
    path_entries = db.execute(
        select(SimulationTaskPath).where(SimulationTaskPath.simulation_id == simulation.id)
    ).scalars().all()
    
    if path_entries:
        total_tasks = len(path_entries)
        completed_tasks = sum(1 for entry in path_entries if entry.task.status == TaskStatus.COMPLETED)
        
        for entry in path_entries:
            task = entry.task
            is_completed = task.status == TaskStatus.COMPLETED
            scenario_progress.append({
                "task_id": str(task.id),
                "title": task.title,
                "status": task.status.value,
                "sequence": entry.sequence,
                "completed": is_completed,
            })
    else:
        for scenario in simulation.scenarios:
            scenario_total = 0
            scenario_completed = 0
            task_details = []
            
            for scenario_task in scenario.tasks:
                scenario_total += 1
                total_tasks += 1
                task = scenario_task.task
                is_completed = task.status == TaskStatus.COMPLETED
                if is_completed:
                    scenario_completed += 1
                    completed_tasks += 1
                
                task_details.append({
                    "task_id": str(task.id),
                    "title": task.title,
                    "status": task.status.value,
                    "sequence": scenario_task.sequence,
                    "completed": is_completed,
                })
            
            scenario_progress.append({
                "scenario_id": str(scenario.id),
                "title": scenario.title,
                "status": scenario.status.value,
                "sequence": scenario.sequence,
                "total_tasks": scenario_total,
                "completed_tasks": scenario_completed,
                "progress_percentage": (scenario_completed / scenario_total * 100) if scenario_total > 0 else 0,
                "tasks": task_details,
            })
    
    overall_progress = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    return {
        "simulation_id": str(simulation.id),
        "status": simulation.status.value,
        "overall_progress": overall_progress,
        "total_tasks": total_tasks,
        "completed_tasks": completed_tasks,
        "remaining_tasks": total_tasks - completed_tasks,
        "current_scenario_id": str(simulation.current_scenario_id) if simulation.current_scenario_id else None,
        "current_task_id": str(simulation.current_task_id) if simulation.current_task_id else None,
        "started_at": simulation.started_at.isoformat() if simulation.started_at else None,
        "completed_at": simulation.completed_at.isoformat() if simulation.completed_at else None,
        "scenarios": scenario_progress,
    }


@router.get("/{simulation_id}/task-path")
def get_task_path(
    simulation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Return the student's personalised ordered task path for this simulation."""
    simulation = _get_owned_simulation(simulation_id, db, user)

    from app.services.simulation.task_path_builder import get_task_path as _get_task_path

    entries = _get_task_path(db, simulation_id)
    return [
        {
            "sequence": entry.sequence,
            "task_id": str(entry.task_id),
            "status": entry.status.value,
            "title": entry.task.title,
            "sprint_id": str(entry.task.sprint_id),
            "estimated_hours": entry.task.estimated_hours,
            "priority": entry.task.priority.value,
        }
        for entry in entries
    ]


def _sync_current_scenario_from_task(db: Session, simulation, task) -> None:
    """Update current_scenario_id if the task belongs to a different scenario."""
    from app.models.simulation import ScenarioTask as ST
    scenario_link = db.execute(
        select(ST)
        .join(Scenario, Scenario.id == ST.scenario_id)
        .where(ST.task_id == task.id, Scenario.simulation_id == simulation.id)
    ).scalar_one_or_none()
    if scenario_link and scenario_link.scenario_id != simulation.current_scenario_id:
        simulation.current_scenario_id = scenario_link.scenario_id


def _format_remaining_time(seconds: float) -> str:
    """Format remaining seconds into human-readable string."""
    if seconds <= 0:
        return "Expired"
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


@router.get("/{simulation_id}/scenario")
def get_current_scenario(
    simulation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get the current active scenario with full details."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    if not simulation.current_scenario_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No active scenario for this simulation"
        )
    
    scenario = db.get(Scenario, simulation.current_scenario_id)
    if not scenario:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Current scenario not found"
        )
    
    # Get current task
    current_task = None
    if simulation.current_task_id:
        current_task = db.get(Task, simulation.current_task_id)
    
    # Get all tasks for this scenario
    scenario_tasks = []
    for st in scenario.tasks:
        task = st.task
        scenario_tasks.append({
            "task_id": str(task.id),
            "title": task.title,
            "description": task.description,
            "task_type": task.task_type.value if task.task_type else "coding",
            "difficulty": scenario.difficulty.value,
            "status": task.status.value,
            "sequence": st.sequence,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        })
    
    return {
        "scenario_id": str(scenario.id),
        "simulation_id": str(simulation.id),
        "title": scenario.title,
        "description": scenario.description,
        "workplace_context": scenario.workplace_context,
        "role": scenario.role,
        "difficulty": scenario.difficulty.value,
        "required_skills": scenario.required_skills,
        "objectives": scenario.objectives,
        "status": scenario.status.value,
        "sequence": scenario.sequence,
        "current_task": {
            "task_id": str(current_task.id),
            "title": current_task.title,
            "description": current_task.description,
            "instructions": current_task.description,
            "difficulty": scenario.difficulty.value,
            "task_type": current_task.task_type.value if current_task.task_type else "coding",
            "required_skills": scenario.required_skills,
            "expected_output": current_task.acceptance_criteria,
            "deadline": current_task.deadline.isoformat() if current_task.deadline else None,
            "status": current_task.status.value,
            "started_at": current_task.started_at.isoformat() if current_task.started_at else None,
        } if current_task else None,
        "all_tasks": scenario_tasks,
        "total_tasks": len(scenario_tasks),
        "completed_tasks": sum(1 for t in scenario_tasks if t["status"] == "completed"),
    }


@router.get("/{simulation_id}/scenario/{scenario_id}")
def get_scenario_by_id(
    simulation_id: uuid.UUID,
    scenario_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get a specific scenario by ID."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    scenario = db.get(Scenario, scenario_id)
    if not scenario or scenario.simulation_id != simulation_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Scenario not found"
        )
    
    # Get all tasks for this scenario
    scenario_tasks = []
    for st in scenario.tasks:
        task = st.task
        scenario_tasks.append({
            "task_id": str(task.id),
            "title": task.title,
            "description": task.description,
            "task_type": task.task_type.value if task.task_type else "coding",
            "difficulty": scenario.difficulty.value,
            "status": task.status.value,
            "sequence": st.sequence,
            "deadline": task.deadline.isoformat() if task.deadline else None,
            "started_at": task.started_at.isoformat() if task.started_at else None,
            "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        })
    
    return {
        "scenario_id": str(scenario.id),
        "simulation_id": str(simulation.id),
        "title": scenario.title,
        "description": scenario.description,
        "workplace_context": scenario.workplace_context,
        "role": scenario.role,
        "difficulty": scenario.difficulty.value,
        "required_skills": scenario.required_skills,
        "objectives": scenario.objectives,
        "status": scenario.status.value,
        "sequence": scenario.sequence,
        "all_tasks": scenario_tasks,
        "total_tasks": len(scenario_tasks),
        "completed_tasks": sum(1 for t in scenario_tasks if t["status"] == "completed"),
    }


@router.get("/{simulation_id}/tasks")
def get_simulation_tasks(
    simulation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get all tasks for a simulation grouped by scenario."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    all_tasks = []
    current_task_id = simulation.current_task_id
    current_scenario_id = simulation.current_scenario_id
    
    for scenario in simulation.scenarios:
        scenario_is_active = scenario.id == current_scenario_id
        scenario_is_completed = scenario.status == ScenarioStatus.COMPLETED
        
        for scenario_task in scenario.tasks:
            task = scenario_task.task
            is_current = str(task.id) == str(current_task_id) if current_task_id else False
            is_completed = task.status == TaskStatus.COMPLETED
            is_future_scenario = not scenario_is_active and not scenario_is_completed
            
            locked = False
            if is_current:
                locked = False
            elif is_completed:
                locked = False
            elif is_future_scenario:
                locked = True
            elif scenario_is_active:
                locked = not is_current
            
            all_tasks.append({
                "task_id": str(task.id),
                "scenario_id": str(scenario.id),
                "scenario_title": scenario.title,
                "title": task.title,
                "description": task.description,
                "task_type": task.task_type.value if task.task_type else None,
                "priority": task.priority.value,
                "status": task.status.value,
                "sequence": scenario_task.sequence,
                "deadline": task.deadline.isoformat() if task.deadline else None,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "estimated_hours": task.estimated_hours,
                "acceptance_criteria": task.acceptance_criteria,
                "is_current": is_current,
                "locked": locked,
            })
    
    return {
        "simulation_id": str(simulation.id),
        "total_tasks": len(all_tasks),
        "tasks": all_tasks,
    }


@router.get("/{simulation_id}/tasks/current")
async def get_current_task(
    simulation_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get the current active task with full details."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    # Auto-recover if current_task_id is missing or points to a completed/deleted task
    task = None
    if simulation.current_task_id:
        task = db.get(Task, simulation.current_task_id)
        # If the current task is missing or completed, find the next one
        if not task or task.status == TaskStatus.COMPLETED:
            task = None
            simulation.current_task_id = None
    
    if not simulation.current_task_id or task is None:
        # Try task path first (personalized path for this student)
        path_entry = db.execute(
            select(SimulationTaskPath)
            .where(
                SimulationTaskPath.simulation_id == simulation_id,
                SimulationTaskPath.status != TaskStatus.COMPLETED,
            )
            .order_by(SimulationTaskPath.sequence)
        ).scalars().first()
        
        if path_entry:
            task = db.get(Task, path_entry.task_id)
            if task and task.status != TaskStatus.COMPLETED:
                simulation.current_task_id = task.id
                # Sync current_scenario_id if the task belongs to a different scenario
                _sync_current_scenario_from_task(db, simulation, task)
                db.add(simulation)
                db.flush()
            else:
                task = None
        
        if not task:
            # Fallback: try progression service
            from app.services.simulation.progression_service import get_next_task_for_simulation
            next_task = await get_next_task_for_simulation(db, simulation)
            if next_task:
                task = next_task
                simulation.current_task_id = next_task.id
                db.add(simulation)
                db.flush()
            else:
                # No more tasks — check if simulation is complete
                if simulation.status == SimulationStatus.IN_PROGRESS:
                    simulation.status = SimulationStatus.COMPLETED
                    simulation.completed_at = datetime.now(timezone.utc)
                    simulation.progress = 100
                    db.add(simulation)
                    db.flush()
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="No active task for this simulation"
                )
    
    # Get current scenario
    current_scenario = None
    if simulation.current_scenario_id:
        current_scenario = db.get(Scenario, simulation.current_scenario_id)
    
    # Calculate remaining time
    remaining_time = None
    deadline_missed = False
    if task.started_at and task.deadline:
        now = datetime.now(timezone.utc)
        if task.deadline > now:
            remaining_seconds = (task.deadline - now).total_seconds()
            remaining_time = {
                "seconds": int(remaining_seconds),
                "minutes": int(remaining_seconds / 60),
                "hours": int(remaining_seconds / 3600),
                "formatted": _format_remaining_time(remaining_seconds)
            }
        else:
            remaining_seconds = (now - task.deadline).total_seconds()
            remaining_time = {
                "seconds": 0,
                "minutes": 0,
                "hours": 0,
                "formatted": "Expired",
                "overdue_seconds": int(remaining_seconds),
                "overdue_formatted": _format_remaining_time(remaining_seconds)
            }
            deadline_missed = True
    
    # Get active workflow event for this task
    active_event = db.execute(
        select(WorkflowEvent)
        .where(
            WorkflowEvent.simulation_id == simulation_id,
            WorkflowEvent.task_id == task.id,
            WorkflowEvent.status.in_(["pending", "acknowledged"])
        )
        .order_by(WorkflowEvent.occurred_at.desc())
    ).scalar_one_or_none()
    
    return {
        "task_id": str(task.id),
        "simulation_id": str(simulation.id),
        "scenario_id": str(current_scenario.id) if current_scenario else None,
        "scenario_title": current_scenario.title if current_scenario else None,
        "title": task.title,
        "description": task.description,
        "instructions": task.description,
        "difficulty": task.difficulty.value if task.difficulty else (current_scenario.difficulty.value if current_scenario else "intermediate"),
        "task_type": task.task_type.value if task.task_type else "coding",
        "required_skills": current_scenario.required_skills if current_scenario else [],
        "expected_output": task.acceptance_criteria,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "status": task.status.value,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
        "estimated_hours": task.estimated_hours,
        "remaining_time": remaining_time,
        "deadline_missed": deadline_missed,
        "active_workplace_event": {
            "id": str(active_event.id),
            "event_type": active_event.event_type.value,
            "title": active_event.title,
            "message": active_event.message,
            "description": active_event.description,
            "occurred_at": active_event.occurred_at.isoformat(),
            "status": active_event.status,
            "action_required": active_event.action_required,
            "original_requirement": active_event.original_requirement,
            "updated_requirement": active_event.updated_requirement,
        } if active_event else None,
    }


def _check_task_unlocked(db: Session, simulation: Simulation, task_id: uuid.UUID) -> None:
    """Enforce current-task-only access. Raises 403 if task is locked."""
    if simulation.current_task_id != task_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Task is locked. Only the current active task can be accessed.",
        )

    task = db.get(Task, task_id)
    if task and task.status == TaskStatus.COMPLETED:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Task is completed and locked.",
        )


@router.post("/{simulation_id}/tasks/{task_id}/start", status_code=status.HTTP_200_OK)
async def start_simulation_task(
    simulation_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Start a simulation task: change state to STARTED, record started_at, calculate deadline."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    _check_task_unlocked(db, simulation, task_id)
    
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Validate current task state - must be TODO (equivalent to ASSIGNED)
    if task.status != TaskStatus.TODO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot start task from '{task.status.value}'. Task must be in TODO state."
        )
    
    # Check dependencies
    from app.api.routes.tasks import _check_dependencies
    _check_dependencies(db, task)
    
    # Calculate deadline based on estimated hours (or use existing deadline)
    now = datetime.now(timezone.utc)
    if not task.deadline:
        # Default deadline: estimated_hours from now, minimum 30 minutes
        import math
        deadline_hours = max(task.estimated_hours, 0.5)
        from datetime import timedelta
        task.deadline = now + timedelta(hours=deadline_hours)
    
    # Transition: TODO -> IN_PROGRESS (which maps to STARTED -> IN_PROGRESS in simulation state machine)
    task.status = TaskStatus.IN_PROGRESS
    task.started_at = now
    
    # Update simulation progress
    simulation.current_task_id = task.id
    
    db.add(task)
    db.add(simulation)
    db.flush()
    
    # Log activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor=user.student_id,
        action="simulation_task_started",
        detail=f"Started task '{task.title}' in simulation '{simulation.title}'",
        simulation_id=str(simulation.id),
        task_id=str(task.id),
        started_at=now.isoformat(),
        deadline=task.deadline.isoformat(),
    )
    
    # Trigger TASK_STARTED event
    from app.services.engines.events_engine import trigger_event
    from app.models.enums import EventType
    project = db.get(Project, simulation.project_id)
    if project:
        await trigger_event(
            db,
            project,
            EventType.TASK_STARTED,
            f"Task '{task.title}' started",
            {"task_id": str(task.id), "task_title": task.title},
        )
    
    db.commit()
    db.refresh(task)
    db.refresh(simulation)
    
    # Check and trigger workflow events (deadline warning, etc.)
    current_scenario = None
    if simulation.current_scenario_id:
        current_scenario = db.get(Scenario, simulation.current_scenario_id)
    
    from app.services.engines import check_and_trigger_workflow_events
    await check_and_trigger_workflow_events(db, simulation, task, current_scenario)
    
    # Return updated task with time tracking info
    remaining_time = None
    if task.started_at and task.deadline:
        remaining_seconds = (task.deadline - now).total_seconds()
        remaining_time = {
            "seconds": int(remaining_seconds),
            "minutes": int(remaining_seconds / 60),
            "hours": int(remaining_seconds / 3600),
            "formatted": _format_remaining_time(remaining_seconds)
        }
    
    return {
        "task_id": str(task.id),
        "simulation_id": str(simulation.id),
        "scenario_id": str(current_scenario.id) if current_scenario else None,
        "title": task.title,
        "description": task.description,
        "instructions": task.description,
        "difficulty": task.difficulty.value if task.difficulty else (current_scenario.difficulty.value if current_scenario else "intermediate"),
        "task_type": task.task_type.value if task.task_type else "coding",
        "required_skills": current_scenario.required_skills if current_scenario else [],
        "expected_output": task.acceptance_criteria,
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "status": task.status.value,
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "estimated_hours": task.estimated_hours,
        "remaining_time": remaining_time,
        "message": "Task started successfully. Timer is running."
    }


@router.post("/{simulation_id}/tasks/{task_id}/submit", status_code=status.HTTP_201_CREATED)
async def submit_simulation_task(
    simulation_id: uuid.UUID,
    task_id: uuid.UUID,
    files: List[UploadFile] = File(default=[]),
    metadata: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Submit a simulation task for evaluation - captures evidence for Member 3."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    _check_task_unlocked(db, simulation, task_id)
    
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found"
        )
    
    # Validate task state - must be IN_PROGRESS to submit
    if task.status != TaskStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot submit task from '{task.status.value}'. Task must be IN_PROGRESS."
        )
    
    if not task.started_at:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Task was not started. Cannot submit without start time."
        )
    
    now = datetime.now(timezone.utc)
    submitted_at = now
    
    # Calculate time taken
    time_taken_seconds = (submitted_at - task.started_at).total_seconds()
    time_taken_minutes = int(time_taken_seconds / 60)
    
    # Check if on time
    on_time = True
    deadline_missed = False
    if task.deadline and submitted_at > task.deadline:
        on_time = False
        deadline_missed = True
    
    # Parse metadata
    import json
    meta_dict = {}
    if metadata:
        try:
            meta_dict = json.loads(metadata)
        except json.JSONDecodeError:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid metadata JSON")
    
    # Prepare file data for storage service
    file_data = []
    for upload_file in files:
        content = await upload_file.read()
        import io
        file_data.append({
            "file": io.BytesIO(content),
            "filename": upload_file.filename,
            "content_type": upload_file.content_type,
        })
    
    # Get project for submission service
    project = db.get(Project, simulation.project_id)
    
    # Store submission using existing submission service
    service = SubmissionService()
    try:
        result = service.store_submission(
            db=db,
            project=project,
            task=task,
            files=file_data,
            metadata=meta_dict,
        )
    except FileValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    
    # Update task status to COMPLETED directly on submit
    task.status = TaskStatus.COMPLETED
    task.completed_at = submitted_at
    if not task.deliverable_url and result.get("submission_id"):
        task.deliverable_url = f"submission://{result['submission_id']}"
    db.add(task)

    # Mark task path entry as completed
    path_entry = db.execute(
        select(SimulationTaskPath).where(
            SimulationTaskPath.simulation_id == simulation_id,
            SimulationTaskPath.task_id == task_id,
        )
    ).scalar_one_or_none()
    if path_entry:
        path_entry.status = TaskStatus.COMPLETED
        path_entry.completed_at = submitted_at
        db.add(path_entry)
    
    # Update simulation progress
    simulation.progress = _calculate_simulation_progress(db, simulation)
    db.add(simulation)
    db.flush()
    
    # Auto-progress to next task
    from app.services.simulation.progression_service import progress_to_next_task
    next_task = await progress_to_next_task(db, simulation, task, user.student_id)
    
    # Collect workflow events encountered during this task
    from app.services.engines import get_task_workflow_events
    workflow_events = await get_task_workflow_events(db, simulation_id, task_id)
    
    events_encountered = []
    requirement_changes_encountered = []
    event_responses = []
    
    for event in workflow_events:
        event_data = {
            "event_id": str(event.id),
            "event_type": event.event_type.value,
            "title": event.title,
            "message": event.message,
            "occurred_at": event.occurred_at.isoformat(),
            "status": event.status,
            "responded": event.response is not None,
            "response": event.response,
            "responded_at": event.responded_at.isoformat() if event.responded_at else None,
        }
        events_encountered.append(event_data)
        
        if event.event_type == WorkflowEventType.REQUIREMENT_CHANGE:
            requirement_changes_encountered.append({
                "original_requirement": event.original_requirement,
                "updated_requirement": event.updated_requirement,
                "trigger_condition": event.trigger_condition,
            })
        
        if event.response:
            event_responses.append({
                "event_id": str(event.id),
                "event_type": event.event_type.value,
                "response": event.response,
                "responded_at": event.responded_at.isoformat() if event.responded_at else None,
            })
    
    # Log activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor=user.student_id,
        action="simulation_task_submitted",
        detail=f"Submitted task '{task.title}' for evaluation",
        simulation_id=str(simulation.id),
        task_id=str(task.id),
        submission_id=result.get("submission_id"),
        version_id=result.get("version_id"),
        time_taken_minutes=time_taken_minutes,
        on_time=on_time,
        deadline_missed=deadline_missed,
    )
    
    # Trigger SUBMISSION_CREATED event
    from app.services.engines.events_engine import trigger_event
    from app.models.enums import EventType
    if project:
        await trigger_event(
            db,
            project,
            EventType.SUBMISSION_CREATED,
            f"Submission created for task '{task.title}'",
            {"task_id": str(task.id), "submission_id": result.get("submission_id"), "version_id": result.get("version_id")},
        )
        await trigger_event(
            db,
            project,
            EventType.SUBMISSION_VERSION_CREATED,
            f"Submission version {result.get('version')} created for task '{task.title}'",
            {"task_id": str(task.id), "version_id": result.get("version_id"), "version": result.get("version")},
        )
    
    db.commit()
    db.refresh(task)
    db.refresh(simulation)
    
    # Build evaluation-ready evidence for Member 3
    current_scenario = None
    if simulation.current_scenario_id:
        current_scenario = db.get(Scenario, simulation.current_scenario_id)
    
    evaluation_evidence = {
        "submission_id": result.get("submission_id"),
        "version_id": result.get("version_id"),
        "task_id": str(task.id),
        "simulation_id": str(simulation.id),
        "user_id": user.student_id,
        "response": meta_dict.get("response", ""),
        "files": result.get("stored_files", []),
        "started_at": task.started_at.isoformat() if task.started_at else None,
        "submitted_at": submitted_at.isoformat(),
        "time_taken_minutes": time_taken_minutes,
        "time_taken_seconds": int(time_taken_seconds),
        "deadline": task.deadline.isoformat() if task.deadline else None,
        "on_time": on_time,
        "deadline_missed": deadline_missed,
        "attempt_number": result.get("version", 1),
        "task_version": result.get("version", 1),
        "events_encountered": events_encountered,
        "requirement_changes_encountered": requirement_changes_encountered,
        "event_responses": event_responses,
        "task_difficulty": task.difficulty.value if task.difficulty else (current_scenario.difficulty.value if current_scenario else "intermediate"),
        "task_type": task.task_type.value if task.task_type else "coding",
        "required_skills": current_scenario.required_skills if current_scenario else [],
        "acceptance_criteria": task.acceptance_criteria,
        "task_state_history": [
            {"status": "TODO", "timestamp": task.started_at.isoformat() if task.started_at else None},
            {"status": "IN_PROGRESS", "timestamp": task.started_at.isoformat() if task.started_at else None},
            {"status": "COMPLETED", "timestamp": submitted_at.isoformat()},
        ],
    }
    
    return {
        "status": "completed",
        "task_id": str(task.id),
        "submission_id": result.get("submission_id"),
        "version_id": result.get("version_id"),
        "submitted_at": submitted_at.isoformat(),
        "time_taken_minutes": time_taken_minutes,
        "on_time": on_time,
        "deadline_missed": deadline_missed,
        "progress": simulation.progress,
        "next_task": {
            "task_id": str(next_task.id),
            "title": next_task.title,
            "description": next_task.description,
        } if next_task else None,
        "simulation_completed": simulation.status == SimulationStatus.COMPLETED,
        "message": "Task completed successfully." if simulation.status == SimulationStatus.COMPLETED else "Task completed. Moving to next task.",
    }


@router.post("/{simulation_id}/tasks/{task_id}/events/{event_id}/respond", status_code=status.HTTP_200_OK)
async def respond_to_simulation_event(
    simulation_id: uuid.UUID,
    task_id: uuid.UUID,
    event_id: uuid.UUID,
    response: str = Form(...),
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Respond to a workflow event (requirement change, deadline warning, etc.)."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    event = db.get(WorkflowEvent, event_id)
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    
    if event.simulation_id != simulation_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Event does not belong to this simulation")
    
    if event.task_id != task_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Event does not belong to this task")
    
    # Record response
    from app.services.engines import respond_to_workflow_event
    updated_event = await respond_to_workflow_event(db, event_id, response, user.student_id)
    
    db.commit()
    db.refresh(updated_event)
    
    return {
        "event_id": str(updated_event.id),
        "status": updated_event.status,
        "response": updated_event.response,
        "responded_at": updated_event.responded_at.isoformat() if updated_event.responded_at else None,
        "message": "Response recorded successfully"
    }


@router.get("/{simulation_id}/tasks/{task_id}/events")
def get_task_events(
    simulation_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Get all workflow events encountered during a task."""
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    events = db.execute(
        select(WorkflowEvent)
        .where(
            WorkflowEvent.simulation_id == simulation_id,
            WorkflowEvent.task_id == task_id,
        )
        .order_by(WorkflowEvent.occurred_at)
    ).scalars().all()
    
    return {
        "task_id": str(task_id),
        "simulation_id": str(simulation_id),
        "events": [
            {
                "id": str(event.id),
                "event_type": event.event_type.value,
                "title": event.title,
                "message": event.message,
                "description": event.description,
                "occurred_at": event.occurred_at.isoformat(),
                "status": event.status,
                "action_required": event.action_required,
                "original_requirement": event.original_requirement,
                "updated_requirement": event.updated_requirement,
                "responded": event.response is not None,
                "response": event.response,
                "responded_at": event.responded_at.isoformat() if event.responded_at else None,
            }
            for event in events
        ],
    }


def _calculate_simulation_progress(db: Session, simulation: Simulation) -> int:
    """Calculate overall simulation progress percentage.
    
    When task paths exist (student-specific task subsets), count from those.
    Otherwise fall back to canonical scenario tasks.
    """
    path_entries = db.execute(
        select(SimulationTaskPath).where(SimulationTaskPath.simulation_id == simulation.id)
    ).scalars().all()

    if path_entries:
        total_tasks = len(path_entries)
        completed_tasks = sum(1 for entry in path_entries if entry.task.status == TaskStatus.COMPLETED)
    else:
        total_tasks = 0
        completed_tasks = 0
        if simulation.scenarios:
            for scenario in simulation.scenarios:
                for scenario_task in scenario.tasks:
                    total_tasks += 1
                    if scenario_task.task.status == TaskStatus.COMPLETED:
                        completed_tasks += 1

    return int((completed_tasks / total_tasks * 100)) if total_tasks > 0 else 0


@router.post("/{simulation_id}/tasks/{task_id}/complete", status_code=status.HTTP_200_OK)
async def complete_simulation_task(
    simulation_id: uuid.UUID,
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Complete a simulation task (called by Member 3 after evaluation approves the task).
    This triggers automatic progression to the next task/scenario.
    """
    simulation = _get_owned_simulation(simulation_id, db, user)
    
    _check_task_unlocked(db, simulation, task_id)
    
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    
    # Validate task state - must be SUBMITTED or UNDER_REVIEW to complete
    if task.status not in [TaskStatus.SUBMITTED, TaskStatus.UNDER_REVIEW]:
        # If already completed, this is a no-op (progression may have already run)
        if task.status == TaskStatus.COMPLETED:
            return {
                "status": "already_completed",
                "task_id": str(task.id),
                "message": "Task was already completed",
            }
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot complete task from '{task.status.value}'. Task must be SUBMITTED or UNDER_REVIEW."
        )
    
    # Mark task as completed
    previous_status = task.status
    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)
    db.add(task)

    # Mark task path entry as completed
    path_entry = db.execute(
        select(SimulationTaskPath).where(
            SimulationTaskPath.simulation_id == simulation_id,
            SimulationTaskPath.task_id == task_id,
        )
    ).scalar_one_or_none()
    if path_entry:
        path_entry.status = TaskStatus.COMPLETED
        path_entry.completed_at = task.completed_at
        db.add(path_entry)
    
    # Update simulation progress
    simulation.progress = _calculate_simulation_progress(db, simulation)
    db.add(simulation)
    db.flush()
    
    # Log activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor=user.student_id,
        action="simulation_task_completed",
        detail=f"Completed task '{task.title}' in simulation '{simulation.title}'",
        simulation_id=str(simulation.id),
        task_id=str(task.id),
        previous_status=previous_status.value,
        new_status=TaskStatus.COMPLETED.value,
    )
    
    # Trigger task completion event
    from app.services.engines.events_engine import trigger_event
    from app.models.enums import EventType
    project = db.get(Project, simulation.project_id)
    if project:
        await trigger_event(
            db,
            project,
            EventType.TASK_COMPLETED,
            f"Task '{task.title}' completed",
            {"task_id": str(task.id), "task_title": task.title},
        )
    
    # Progress to next task/scenario
    from app.services.simulation.progression_service import progress_to_next_task
    next_task = await progress_to_next_task(db, simulation, task, user.student_id)
    
    db.commit()
    db.refresh(simulation)
    
    # Check if simulation is complete
    if simulation.status == SimulationStatus.COMPLETED:
        return {
            "status": "simulation_completed",
            "simulation_id": str(simulation.id),
            "completed_at": simulation.completed_at.isoformat() if simulation.completed_at else None,
            "message": "Simulation completed successfully! All scenarios and tasks are done.",
        }
    
    # Return next task info
    next_task_info = None
    current_scenario = None
    if simulation.current_scenario_id:
        current_scenario = db.get(Scenario, simulation.current_scenario_id)
    
    if next_task:
        db.refresh(next_task)
        remaining_time = None
        if next_task.deadline:
            now = datetime.now(timezone.utc)
            if next_task.deadline > now:
                remaining_seconds = (next_task.deadline - now).total_seconds()
                remaining_time = {
                    "seconds": int(remaining_seconds),
                    "minutes": int(remaining_seconds / 60),
                    "hours": int(remaining_seconds / 3600),
                    "formatted": _format_remaining_time(remaining_seconds)
                }
        
        next_task_info = {
            "task_id": str(next_task.id),
            "title": next_task.title,
            "description": next_task.description,
            "instructions": next_task.description,
            "difficulty": next_task.difficulty.value if next_task.difficulty else (current_scenario.difficulty.value if current_scenario else "intermediate"),
            "task_type": next_task.task_type.value if next_task.task_type else "coding",
            "required_skills": current_scenario.required_skills if current_scenario else [],
            "expected_output": next_task.acceptance_criteria,
            "deadline": next_task.deadline.isoformat() if next_task.deadline else None,
            "status": next_task.status.value,
            "estimated_hours": next_task.estimated_hours,
            "remaining_time": remaining_time,
        }
    
    return {
        "status": "task_completed",
        "simulation_id": str(simulation.id),
        "completed_task_id": str(task.id),
        "progress": simulation.progress,
        "next_task": next_task_info,
        "current_scenario": {
            "id": str(current_scenario.id),
            "title": current_scenario.title,
            "status": current_scenario.status.value,
        } if current_scenario else None,
        "message": "Task completed. Progressed to next task." if next_task else "All tasks in scenario completed. Moving to next scenario.",
    }