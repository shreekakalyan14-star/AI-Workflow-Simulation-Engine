"""
Task Path Builder - creates personalized task paths for each student.

Canonical tasks in sprints are shared templates. This service creates a
per-student subset of those tasks, ordered by sprint and sequence, allowing
different students to receive different numbers of project-relevant tasks.
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import TaskStatus
from app.models.sprint import Sprint
from app.models.task import Task
from app.models.task_path import SimulationTaskPath
from app.models.simulation import Simulation


def get_canonical_tasks_for_project(db: Session, project_id: UUID) -> List[Task]:
    """Fetch all canonical tasks belonging to a project, ordered by sprint then sequence."""
    return db.execute(
        select(Task)
        .join(Sprint, Sprint.id == Task.sprint_id)
        .where(Sprint.project_id == project_id)
        .order_by(Sprint.sprint_number, Task.sequence)
    ).scalars().all()


def build_task_path(
    db: Session,
    simulation_id: UUID,
    project_id: UUID,
    task_ids: Optional[List[UUID]] = None,
) -> List[SimulationTaskPath]:
    """Create a personalized task path for a simulation.

    Args:
        db: Database session
        simulation_id: The student's simulation
        project_id: The project whose tasks to draw from
        task_ids: Optional explicit list of canonical task IDs to include.
                  If None, all canonical tasks for the project are used.

    Returns:
        List of created SimulationTaskPath entries, ordered by sequence.
    """
    if task_ids is not None:
        # Use explicitly selected tasks
        tasks = []
        for tid in task_ids:
            task = db.get(Task, tid)
            if task and task.sprint_id:
                sprint = db.get(Sprint, task.sprint_id)
                if sprint and sprint.project_id == project_id:
                    tasks.append(task)
        # Sort by sprint number then sequence
        tasks.sort(key=lambda t: (
            _get_sprint_number(db, t.sprint_id),
            t.sequence,
        ))
    else:
        tasks = get_canonical_tasks_for_project(db, project_id)

    path_entries: List[SimulationTaskPath] = []
    for idx, task in enumerate(tasks, start=1):
        entry = SimulationTaskPath(
            simulation_id=simulation_id,
            task_id=task.id,
            sequence=idx,
            status=TaskStatus.BACKLOG,
        )
        db.add(entry)
        path_entries.append(entry)

    db.flush()
    return path_entries


def get_task_path(db: Session, simulation_id: UUID) -> List[SimulationTaskPath]:
    """Get the ordered task path for a simulation."""
    return db.execute(
        select(SimulationTaskPath)
        .where(SimulationTaskPath.simulation_id == simulation_id)
        .order_by(SimulationTaskPath.sequence)
    ).scalars().all()


def get_current_path_entry(
    db: Session, simulation_id: UUID
) -> Optional[SimulationTaskPath]:
    """Get the first non-completed task path entry for a simulation."""
    return db.execute(
        select(SimulationTaskPath)
        .where(
            SimulationTaskPath.simulation_id == simulation_id,
            SimulationTaskPath.status != TaskStatus.COMPLETED,
        )
        .order_by(SimulationTaskPath.sequence)
    ).scalars().first()


def _get_sprint_number(db: Session, sprint_id: UUID) -> int:
    sprint = db.get(Sprint, sprint_id)
    return sprint.sprint_number if sprint else 0
