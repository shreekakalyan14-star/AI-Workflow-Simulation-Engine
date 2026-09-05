"""
Workflow Events Engine - deterministic event triggering for simulations.

Handles:
- REQUIREMENT_CHANGE events
- DEADLINE_WARNING events
- Event history and responses
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import WorkflowEventType, TaskStatus
from app.models.simulation import Simulation, Scenario, WorkflowEvent
from app.models.task import Task
from app.services.engines.simulation_task_state_machine import SimulationTaskState


REQUIREMENT_CHANGE_TRIGGER_STAGE = 0.3  # Trigger at 30% of task duration
DEADLINE_WARNING_THRESHOLD_MINUTES = 5  # Warn 5 minutes before deadline


async def trigger_requirement_change_event(
    db: Session,
    simulation: Simulation,
    task: Task,
    scenario: Scenario,
    original_requirement: str,
    updated_requirement: str,
    trigger_condition: str = "task_progress",
) -> WorkflowEvent:
    """Create a REQUIREMENT_CHANGE workflow event."""
    event = WorkflowEvent(
        simulation_id=simulation.id,
        task_id=task.id,
        scenario_id=scenario.id if scenario else None,
        event_type=WorkflowEventType.REQUIREMENT_CHANGE,
        title="Requirement Change",
        message="The requirements for this task have been updated.",
        description=(
            f"Original requirement: {original_requirement}\n\n"
            f"Updated requirement: {updated_requirement}"
        ),
        original_requirement=original_requirement,
        updated_requirement=updated_requirement,
        trigger_condition=trigger_condition,
        action_required=True,
        occurred_at=datetime.now(timezone.utc),
        status="pending",
        metadata_json={
            "trigger_stage": REQUIREMENT_CHANGE_TRIGGER_STAGE,
            "task_type": task.task_type.value if task.task_type else None,
        },
    )
    db.add(event)
    db.flush()
    
    # Log activity
    from app.services.activity_log_service import log_activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor="system",
        action="requirement_change_event",
        detail=f"Requirement change event triggered for task '{task.title}'",
        simulation_id=str(simulation.id),
        task_id=str(task.id),
        event_id=str(event.id),
    )
    
    return event


async def trigger_deadline_warning_event(
    db: Session,
    simulation: Simulation,
    task: Task,
    scenario: Scenario,
    remaining_minutes: int,
) -> WorkflowEvent:
    """Create a DEADLINE_WARNING workflow event."""
    event = WorkflowEvent(
        simulation_id=simulation.id,
        task_id=task.id,
        scenario_id=scenario.id if scenario else None,
        event_type=WorkflowEventType.DEADLINE_WARNING,
        title="Deadline Warning",
        message=f"You have {remaining_minutes} minutes remaining to complete this task. Please submit your work before the deadline.",
        description=(
            f"Task: {task.title}\n"
            f"Deadline: {task.deadline.isoformat() if task.deadline else 'Not set'}\n"
            f"Time remaining: {remaining_minutes} minutes"
        ),
        trigger_condition=f"deadline_approaching_{remaining_minutes}_minutes",
        action_required=False,
        occurred_at=datetime.now(timezone.utc),
        status="pending",
        metadata_json={
            "remaining_minutes": remaining_minutes,
            "threshold_minutes": DEADLINE_WARNING_THRESHOLD_MINUTES,
        },
    )
    db.add(event)
    db.flush()
    
    # Log activity
    from app.services.activity_log_service import log_activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor="system",
        action="deadline_warning_event",
        detail=f"Deadline warning event triggered for task '{task.title}' ({remaining_minutes} minutes remaining)",
        simulation_id=str(simulation.id),
        task_id=str(task.id),
        event_id=str(event.id),
    )
    
    return event


async def check_and_trigger_workflow_events(
    db: Session,
    simulation: Simulation,
    task: Task,
    scenario: Optional[Scenario] = None,
) -> list[WorkflowEvent]:
    """Check conditions and trigger appropriate workflow events deterministically."""
    triggered_events = []
    
    if not task.started_at or not task.deadline:
        return triggered_events
    
    now = datetime.now(timezone.utc)
    
    # Check for deadline warning
    if task.deadline > now:
        remaining_seconds = (task.deadline - now).total_seconds()
        remaining_minutes = int(remaining_seconds / 60)
        
        # Trigger warning at threshold
        if remaining_minutes <= DEADLINE_WARNING_THRESHOLD_MINUTES:
            # Check if warning already triggered for this threshold
            existing_warning = db.execute(
                select(WorkflowEvent)
                .where(
                    WorkflowEvent.simulation_id == simulation.id,
                    WorkflowEvent.task_id == task.id,
                    WorkflowEvent.event_type == WorkflowEventType.DEADLINE_WARNING,
                    WorkflowEvent.metadata_json["remaining_minutes"].astext.cast(int) == remaining_minutes
                )
            ).scalar_one_or_none()
            
            if not existing_warning:
                event = await trigger_deadline_warning_event(
                    db, simulation, task, scenario, remaining_minutes
                )
                triggered_events.append(event)
    
    # Check for requirement change (triggered at 30% task progress)
    if task.started_at and scenario:
        # Count total and completed tasks for the current scenario
        from app.models.simulation import ScenarioTask
        
        scenario_tasks = db.execute(
            select(ScenarioTask)
            .where(ScenarioTask.scenario_id == scenario.id)
        ).scalars().all()
        
        total_tasks = len(scenario_tasks)
        if total_tasks > 0:
            completed_count = 0
            for st in scenario_tasks:
                t = db.get(Task, st.task_id)
                if t and t.status in (TaskStatus.COMPLETED, TaskStatus.UNDER_REVIEW, TaskStatus.MANAGER_APPROVAL):
                    completed_count += 1
            
            progress_ratio = completed_count / total_tasks
            
            if progress_ratio >= REQUIREMENT_CHANGE_TRIGGER_STAGE:
                # Check if requirement change already triggered for this scenario
                existing_rc = db.execute(
                    select(WorkflowEvent)
                    .where(
                        WorkflowEvent.simulation_id == simulation.id,
                        WorkflowEvent.scenario_id == scenario.id,
                        WorkflowEvent.event_type == WorkflowEventType.REQUIREMENT_CHANGE,
                    )
                ).scalar_one_or_none()
                
                if not existing_rc:
                    event = await trigger_requirement_change_event(
                        db, simulation, task, scenario,
                        original_requirement=f"Original requirement for {scenario.title}",
                        updated_requirement=f"Updated requirement: The scope has been expanded to include additional {scenario.role} responsibilities.",
                        trigger_condition="task_progress_30_percent",
                    )
                    triggered_events.append(event)
    
    return triggered_events


async def trigger_workflow_event(
    db: Session,
    simulation_id: UUID,
    event_type: WorkflowEventType,
    title: str,
    message: str,
    task_id: Optional[UUID] = None,
    scenario_id: Optional[UUID] = None,
    description: Optional[str] = None,
    original_requirement: Optional[str] = None,
    updated_requirement: Optional[str] = None,
    trigger_condition: Optional[str] = None,
    action_required: bool = False,
    metadata: Optional[dict] = None,
) -> WorkflowEvent:
    """Generic function to trigger a workflow event."""
    simulation = db.get(Simulation, simulation_id)
    if not simulation:
        raise ValueError("Simulation not found")
    
    event = WorkflowEvent(
        simulation_id=simulation_id,
        task_id=task_id,
        scenario_id=scenario_id,
        event_type=event_type,
        title=title,
        message=message,
        description=description,
        original_requirement=original_requirement,
        updated_requirement=updated_requirement,
        trigger_condition=trigger_condition,
        action_required=action_required,
        occurred_at=datetime.now(timezone.utc),
        status="pending",
        metadata_json=metadata or {},
    )
    db.add(event)
    db.flush()
    
    # Log activity
    from app.services.activity_log_service import log_activity
    log_activity(
        db,
        company_id=simulation.company_id,
        actor="system",
        action=f"workflow_event_{event_type.value.lower()}",
        detail=f"{title} event triggered: {message}",
        simulation_id=str(simulation_id),
        task_id=str(task_id) if task_id else None,
        event_id=str(event.id),
    )
    
    return event


async def respond_to_workflow_event(
    db: Session,
    event_id: UUID,
    response: str,
    user_id: str,
) -> WorkflowEvent:
    """Record a student's response to a workflow event."""
    event = db.get(WorkflowEvent, event_id)
    if not event:
        raise ValueError("Workflow event not found")
    
    event.response = response
    event.responded_at = datetime.now(timezone.utc)
    event.status = "acknowledged"
    event.metadata_json = event.metadata_json or {}
    event.metadata_json["responded_by"] = user_id
    
    db.add(event)
    db.flush()
    
    # Log activity
    simulation = db.get(Simulation, event.simulation_id)
    if simulation:
        from app.services.activity_log_service import log_activity
        log_activity(
            db,
            company_id=simulation.company_id,
            actor=user_id,
            action="workflow_event_response",
            detail=f"Responded to {event.event_type.value} event: {response}",
            simulation_id=str(event.simulation_id),
            task_id=str(event.task_id) if event.task_id else None,
            event_id=str(event.id),
        )
    
    return event


async def get_task_workflow_events(
    db: Session,
    simulation_id: UUID,
    task_id: UUID,
) -> list[WorkflowEvent]:
    """Get all workflow events for a specific task."""
    return db.execute(
        select(WorkflowEvent)
        .where(
            WorkflowEvent.simulation_id == simulation_id,
            WorkflowEvent.task_id == task_id,
        )
        .order_by(WorkflowEvent.occurred_at)
    ).scalars().all()


async def get_simulation_workflow_events(
    db: Session,
    simulation_id: UUID,
) -> list[WorkflowEvent]:
    """Get all workflow events for a simulation."""
    return db.execute(
        select(WorkflowEvent)
        .where(WorkflowEvent.simulation_id == simulation_id)
        .order_by(WorkflowEvent.occurred_at)
    ).scalars().all()