"""
Simulation Progression Service - handles automatic task and scenario progression.

When a task becomes COMPLETED:
1. Find next task in current scenario
2. Assign next task (set to TODO)
3. Update simulation current_task
4. Update progress
5. If scenario is complete, move to next scenario
6. If all scenarios/tasks are complete, mark simulation COMPLETED
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ScenarioStatus, SimulationStatus, TaskStatus
from app.models.simulation import Simulation, Scenario, ScenarioTask
from app.models.task import Task
from app.services.activity_log_service import log_activity


async def progress_to_next_task(
    db: Session,
    simulation: Simulation,
    completed_task: Task,
    user_id: str,
) -> Optional[Task]:
    """
    Progress to the next task after current task is completed.
    Returns the next task if found, None if simulation is complete.
    """
    from app.models.task_path import SimulationTaskPath

    # Check if task paths are in use for this simulation
    completed_path_entry = db.execute(
        select(SimulationTaskPath)
        .where(
            SimulationTaskPath.simulation_id == simulation.id,
            SimulationTaskPath.task_id == completed_task.id,
        )
    ).scalar_one_or_none()

    if completed_path_entry:
        # Find next task in the path
        next_path_entry = db.execute(
            select(SimulationTaskPath)
            .join(Task, Task.id == SimulationTaskPath.task_id)
            .where(
                SimulationTaskPath.simulation_id == simulation.id,
                SimulationTaskPath.sequence > completed_path_entry.sequence,
                Task.status != TaskStatus.COMPLETED,
            )
            .order_by(SimulationTaskPath.sequence)
        ).scalars().first()

        if next_path_entry:
            next_task = db.get(Task, next_path_entry.task_id)
            if next_task:
                if next_task.status == TaskStatus.BACKLOG:
                    next_task.status = TaskStatus.TODO

                simulation.current_task_id = next_task.id
                simulation.progress = _calculate_simulation_progress(db, simulation)

                # Update current_scenario_id if the next task belongs to a different scenario
                _sync_current_scenario(db, simulation, next_task)

                db.add(next_task)
                db.add(simulation)
                db.flush()

                log_activity(
                    db,
                    company_id=simulation.company_id,
                    actor=user_id,
                    action="simulation_task_progressed",
                    detail=f"Progressed to next task '{next_task.title}' in task path",
                    simulation_id=str(simulation.id),
                    task_id=str(next_task.id),
                    previous_task_id=str(completed_task.id),
                )

                return next_task

        # No more tasks in path - simulation is complete
        return await _complete_simulation(db, simulation, user_id)

    # Fallback to original ScenarioTask-based progression
    if not simulation.current_scenario_id:
        return None
    
    current_scenario = db.get(Scenario, simulation.current_scenario_id)
    if not current_scenario:
        return None
    
    # Find the completed task's sequence in the scenario
    completed_scenario_task = db.execute(
        select(ScenarioTask)
        .where(
            ScenarioTask.scenario_id == current_scenario.id,
            ScenarioTask.task_id == completed_task.id
        )
    ).scalar_one_or_none()
    
    if not completed_scenario_task:
        return None
    
    completed_sequence = completed_scenario_task.sequence
    
    # Find next UNCOMPLETED task in the same scenario (skip already completed tasks)
    next_scenario_task = db.execute(
        select(ScenarioTask)
        .join(Task, Task.id == ScenarioTask.task_id)
        .where(
            ScenarioTask.scenario_id == current_scenario.id,
            ScenarioTask.sequence > completed_sequence,
            Task.status != TaskStatus.COMPLETED,
        )
        .order_by(ScenarioTask.sequence)
    ).scalars().first()
    
    if next_scenario_task:
        # Found next uncompleted task in current scenario
        next_task = db.get(Task, next_scenario_task.task_id)
        if next_task:
            # Assign next task (set to TODO)
            if next_task.status == TaskStatus.BACKLOG:
                next_task.status = TaskStatus.TODO
            
            simulation.current_task_id = next_task.id
            simulation.progress = _calculate_simulation_progress(db, simulation)
            
            db.add(next_task)
            db.add(simulation)
            db.flush()
            
            # Log activity
            log_activity(
                db,
                company_id=simulation.company_id,
                actor=user_id,
                action="simulation_task_progressed",
                detail=f"Progressed to next task '{next_task.title}' in scenario '{current_scenario.title}'",
                simulation_id=str(simulation.id),
                scenario_id=str(current_scenario.id),
                task_id=str(next_task.id),
                previous_task_id=str(completed_task.id),
            )
            
            return next_task
    
    # No more uncompleted tasks in current scenario - check if scenario is truly complete
    return await _progress_to_next_scenario(db, simulation, current_scenario, user_id)


async def _progress_to_next_scenario(
    db: Session,
    simulation: Simulation,
    completed_scenario: Scenario,
    user_id: str,
) -> Optional[Task]:
    """
    Progress to the next scenario after current scenario is verified complete.
    
    IMPORTANT: This function does NOT assume the scenario is complete.
    It verifies that ALL tasks linked through scenario_tasks are COMPLETED
    before marking the scenario as done. If any task is not completed,
    it returns None (scenario stays ACTIVE, current_task_id stays unchanged).
    """
    # Verify ALL scenario tasks are actually completed before marking scenario done
    all_completed = True
    for scenario_task in completed_scenario.tasks:
        task = db.get(Task, scenario_task.task_id)
        if task and task.status != TaskStatus.COMPLETED:
            all_completed = False
            break
    
    if not all_completed:
        # Scenario is NOT complete - do not mark as completed, do not change current_task
        # The caller should not have called this function; return None to signal no progression
        return None
    
    # All tasks confirmed completed - mark scenario as completed
    completed_scenario.status = ScenarioStatus.COMPLETED
    db.add(completed_scenario)
    
    # Find next scenario
    next_scenario = db.execute(
        select(Scenario)
        .where(
            Scenario.simulation_id == simulation.id,
            Scenario.sequence > completed_scenario.sequence
        )
        .order_by(Scenario.sequence)
    ).scalar_one_or_none()
    
    if next_scenario:
        # Found next scenario
        next_scenario.status = ScenarioStatus.ACTIVE
        simulation.current_scenario_id = next_scenario.id
        db.add(next_scenario)
        
        # Find first UNCOMPLETED task in next scenario
        first_scenario_task = db.execute(
            select(ScenarioTask)
            .join(Task, Task.id == ScenarioTask.task_id)
            .where(
                ScenarioTask.scenario_id == next_scenario.id,
                Task.status != TaskStatus.COMPLETED,
            )
            .order_by(ScenarioTask.sequence)
        ).scalars().first()
        
        if first_scenario_task:
            first_task = db.get(Task, first_scenario_task.task_id)
            if first_task:
                # Assign first task of next scenario
                if first_task.status == TaskStatus.BACKLOG:
                    first_task.status = TaskStatus.TODO
                
                simulation.current_task_id = first_task.id
                simulation.progress = _calculate_simulation_progress(db, simulation)
                db.add(first_task)
                
                log_activity(
                    db,
                    company_id=simulation.company_id,
                    actor=user_id,
                    action="simulation_scenario_progressed",
                    detail=f"Progressed to next scenario '{next_scenario.title}' with task '{first_task.title}'",
                    simulation_id=str(simulation.id),
                    scenario_id=str(next_scenario.id),
                    task_id=str(first_task.id),
                    previous_scenario_id=str(completed_scenario.id),
                )
                
                return first_task
        
        # Next scenario has no uncompleted tasks - recursively check next scenario
        return await _progress_to_next_scenario(db, simulation, next_scenario, user_id)
    
    else:
        # No more scenarios - simulation is complete!
        return await _complete_simulation(db, simulation, user_id)


async def _complete_simulation(
    db: Session,
    simulation: Simulation,
    user_id: str,
) -> None:
    """Mark simulation as completed."""
    simulation.status = SimulationStatus.COMPLETED
    simulation.completed_at = datetime.now(timezone.utc)
    simulation.current_task_id = None
    simulation.current_scenario_id = None
    simulation.progress = 100
    db.add(simulation)
    
    # Calculate total duration
    duration_minutes = 0
    if simulation.started_at and simulation.completed_at:
        duration_seconds = (simulation.completed_at - simulation.started_at).total_seconds()
        duration_minutes = int(duration_seconds / 60)
    
    log_activity(
        db,
        company_id=simulation.company_id,
        actor=user_id,
        action="simulation_completed",
        detail=f"Completed simulation '{simulation.title}' in {duration_minutes} minutes",
        simulation_id=str(simulation.id),
        duration_minutes=duration_minutes,
    )


def _calculate_simulation_progress(db: Session, simulation: Simulation) -> int:
    """Calculate overall simulation progress percentage.
    
    When task paths exist (student-specific task subsets), count from those.
    Otherwise fall back to canonical scenario tasks.
    """
    from app.models.task_path import SimulationTaskPath

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


def _sync_current_scenario(db: Session, simulation: Simulation, task: Task) -> None:
    """Update current_scenario_id if the given task belongs to a different scenario."""
    scenario_task = db.execute(
        select(ScenarioTask)
        .join(Scenario, Scenario.id == ScenarioTask.scenario_id)
        .where(
            ScenarioTask.task_id == task.id,
            Scenario.simulation_id == simulation.id,
        )
    ).scalar_one_or_none()

    if scenario_task and scenario_task.scenario_id != simulation.current_scenario_id:
        simulation.current_scenario_id = scenario_task.scenario_id
        db.add(simulation)


async def trigger_requirement_change_for_task(
    db: Session,
    simulation: Simulation,
    task: Task,
    scenario: Scenario,
    original_requirement: str,
    updated_requirement: str,
) -> None:
    """
    Trigger a requirement change event for a task.
    This can be called by the simulation orchestrator or external triggers.
    """
    from app.services.engines import trigger_requirement_change_event
    await trigger_requirement_change_event(
        db,
        simulation,
        task,
        scenario,
        original_requirement,
        updated_requirement,
        trigger_condition="mid_task_progress",
    )


async def check_scenario_completion(db: Session, simulation: Simulation, scenario: Scenario) -> bool:
    """Check if all tasks linked through scenario_tasks are completed."""
    for scenario_task in scenario.tasks:
        task = db.get(Task, scenario_task.task_id)
        if not task or task.status != TaskStatus.COMPLETED:
            return False
    return True


async def get_next_task_for_simulation(db: Session, simulation: Simulation) -> Optional[Task]:
    """Get the next task that should be worked on for a simulation."""
    if not simulation.current_task_id:
        # No current task - find first task of first active scenario
        if not simulation.current_scenario_id:
            # Find first pending/active scenario
            first_scenario = db.execute(
                select(Scenario)
                .where(Scenario.simulation_id == simulation.id)
                .order_by(Scenario.sequence)
            ).scalars().first()
            
            if first_scenario and first_scenario.status in [ScenarioStatus.PENDING, ScenarioStatus.ACTIVE]:
                first_scenario.status = ScenarioStatus.ACTIVE
                simulation.current_scenario_id = first_scenario.id
                db.add(first_scenario)
                db.add(simulation)
                db.flush()
        
        if simulation.current_scenario_id:
            # Find first UNCOMPLETED task in the scenario
            first_scenario_task = db.execute(
                select(ScenarioTask)
                .join(Task, Task.id == ScenarioTask.task_id)
                .where(
                    ScenarioTask.scenario_id == simulation.current_scenario_id,
                    Task.status != TaskStatus.COMPLETED,
                )
                .order_by(ScenarioTask.sequence)
            ).scalars().first()
            
            if first_scenario_task:
                task = db.get(Task, first_scenario_task.task_id)
                if task and task.status == TaskStatus.BACKLOG:
                    task.status = TaskStatus.TODO
                    db.add(task)
                    db.flush()
                simulation.current_task_id = task.id if task else None
                db.add(simulation)
                db.flush()
                return task
    else:
        # Return current task if it's not completed
        current_task = db.get(Task, simulation.current_task_id)
        if current_task and current_task.status != TaskStatus.COMPLETED:
            return current_task
    
    return None