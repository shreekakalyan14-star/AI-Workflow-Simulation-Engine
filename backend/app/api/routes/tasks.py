import uuid
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.enums import TaskStatus
from app.models.project import Project
from app.models.project_state import ProjectState
from app.models.sprint import Sprint
from app.models.task import Task, TaskDependency
from app.schemas.task import TaskRead, TaskStatusUpdate
from app.services.engines import workflow_engine
from app.websockets.manager import manager as ws_manager
from pydantic import BaseModel, Field

router = APIRouter(tags=["Tasks"])


class BugReportRequest(BaseModel):
    description: str = Field(..., min_length=1, examples=["Login form throws a 500 on empty password"])


def _get_owned_task(
    task_id: uuid.UUID,
    db: Session,
    user: CurrentUser,
) -> Task:
    task = db.get(Task, task_id)
    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your task")
    return task


def _to_task_read(task: Task, db: Session) -> TaskRead:
    dep_stmt = select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == task.id)
    dep_ids = db.execute(dep_stmt).scalars().all()
    data = TaskRead.model_validate(task)
    data.depends_on_task_ids = list(dep_ids)
    return data


@router.get("/api/tasks/{task_id}", response_model=TaskRead)
def get_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    task = _get_owned_task(task_id, db, user)
    return _to_task_read(task, db)


@router.get("/api/projects/{project_id}/board", response_model=Dict[str, List[TaskRead]])
def get_kanban_board(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """Every task for the project, grouped by status — feeds the Kanban board columns directly."""
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")

    stmt = (
        select(Task)
        .join(Sprint, Sprint.id == Task.sprint_id)
        .where(Sprint.project_id == project_id)
    )
    tasks = db.execute(stmt).scalars().all()

    board: Dict[str, List[TaskRead]] = {s.value: [] for s in TaskStatus}
    for task in tasks:
        board[task.status.value].append(_to_task_read(task, db))
    return board


@router.patch("/api/tasks/{task_id}/status", response_model=TaskRead)
async def update_task_status(
    task_id: uuid.UUID,
    payload: TaskStatusUpdate,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Drives both the Kanban drag-and-drop (FEATURE 4) and task actions —
    start/pause/complete/block (FEATURE 5). Every transition persists,
    updates the project's live state counters, runs the stateful workflow
    rules (FEATURE 8), and broadcasts the change over WebSocket (FEATURE 17).
    """
    task = _get_owned_task(task_id, db, user)

    if payload.status == TaskStatus.IN_PROGRESS and task.status == TaskStatus.BACKLOG:
        dep_stmt = select(TaskDependency.depends_on_task_id).where(TaskDependency.task_id == task.id)
        dep_ids = db.execute(dep_stmt).scalars().all()
        if dep_ids:
            incomplete = db.execute(
                select(Task.id).where(Task.id.in_(dep_ids), Task.status != TaskStatus.COMPLETED)
            ).scalars().all()
            if incomplete:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Cannot start: one or more dependencies are not completed yet.",
                )

    previous_status = task.status
    task.status = payload.status

    now = datetime.now(timezone.utc)
    if payload.status == TaskStatus.IN_PROGRESS and task.started_at is None:
        task.started_at = now
    if payload.status == TaskStatus.COMPLETED:
        task.completed_at = now
    if payload.status == TaskStatus.BLOCKED:
        task.blocked_reason = payload.blocked_reason or task.blocked_reason
    if payload.deliverable_url:
        task.deliverable_url = payload.deliverable_url

    db.add(task)
    db.flush()

    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    state = db.execute(
        select(ProjectState).where(ProjectState.project_id == project.id)
    ).scalar_one_or_none()

    _sync_project_state(db, task, previous_status, payload.status)

    db.commit()
    db.refresh(task)

    if state is not None:
        await workflow_engine.evaluate_after_task_transition(
            db, task, sprint, project, state, previous_status, payload.status
        )

    await ws_manager.broadcast(
        str(project.company_id),
        "task_updated",
        {"task_id": str(task.id), "status": task.status.value},
    )

    return _to_task_read(task, db)


@router.post("/api/tasks/{task_id}/report-bug", status_code=status.HTTP_201_CREATED)
async def report_bug(
    task_id: uuid.UUID,
    payload: BugReportRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Lets a student flag a bug on a task. Feeds FEATURE 8 (bug_count in
    ProjectState) and FEATURE 9 (fires a BUG_REPORT event, and an
    EMERGENCY_MEETING event once bugs cross the threshold).
    """
    task = _get_owned_task(task_id, db, user)
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    state = db.execute(
        select(ProjectState).where(ProjectState.project_id == project.id)
    ).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project state not found")

    await workflow_engine.report_bug(db, project, state, f"Bug on '{task.title}': {payload.description}")

    await ws_manager.broadcast(
        str(project.company_id), "bug_reported", {"task_id": str(task.id), "description": payload.description}
    )

    return {"status": "reported", "bug_count": state.bug_count}


def _sync_project_state(db: Session, task: Task, previous_status: TaskStatus, new_status: TaskStatus) -> None:
    sprint = db.get(Sprint, task.sprint_id)
    state_stmt = select(ProjectState).where(ProjectState.project_id == sprint.project_id)
    state = db.execute(state_stmt).scalar_one_or_none()
    if state is None:
        return

    if new_status == TaskStatus.COMPLETED and previous_status != TaskStatus.COMPLETED:
        state.completed_tasks += 1
        if task.deadline and task.completed_at and task.completed_at > task.deadline:
            state.missed_deadlines += 1
        if task.started_at and task.completed_at:
            hours = (task.completed_at - task.started_at).total_seconds() / 3600
            # rolling average
            n = max(state.completed_tasks, 1)
            state.avg_completion_time_hours = round(
                ((state.avg_completion_time_hours * (n - 1)) + hours) / n, 2
            )

    remaining_stmt = (
        select(Task)
        .join(Sprint, Sprint.id == Task.sprint_id)
        .where(Sprint.project_id == sprint.project_id, Task.status != TaskStatus.COMPLETED)
    )
    state.pending_tasks = len(db.execute(remaining_stmt).scalars().all())

    db.add(state)
    db.flush()
