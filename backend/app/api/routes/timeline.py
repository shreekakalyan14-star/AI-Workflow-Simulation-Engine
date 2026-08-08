"""
FEATURE 11: Timeline.

Aggregates completed tasks, events, meetings, and chat messages into one
chronological feed for a project — no separate table, just a merge query
across what already exists.
"""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.enums import TaskStatus
from app.models.event import Event
from app.models.message import Message
from app.models.meeting import MeetingSchedule
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.task import Task
from app.schemas.misc import TimelineEntry

router = APIRouter(prefix="/api/projects/{project_id}/timeline", tags=["Timeline"])


@router.get("", response_model=List[TimelineEntry])
def get_timeline(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")

    entries: List[TimelineEntry] = []

    completed_tasks = db.execute(
        select(Task)
        .join(Sprint, Sprint.id == Task.sprint_id)
        .where(Sprint.project_id == project_id, Task.status == TaskStatus.COMPLETED)
    ).scalars().all()
    for t in completed_tasks:
        if t.completed_at:
            entries.append(TimelineEntry(kind="task_completed", title=t.title, timestamp=t.completed_at))

    events = db.execute(select(Event).where(Event.project_id == project_id)).scalars().all()
    for e in events:
        entries.append(TimelineEntry(
            kind="event", title=e.event_type.value.replace("_", " ").title(),
            detail=e.description, timestamp=e.created_at,
        ))

    meetings = db.execute(select(MeetingSchedule).where(MeetingSchedule.project_id == project_id)).scalars().all()
    for m in meetings:
        entries.append(TimelineEntry(
            kind="meeting", title=m.meeting_type.value.replace("_", " ").title(),
            detail=m.agenda, timestamp=m.scheduled_at or m.created_at,
        ))

    messages = db.execute(select(Message).where(Message.company_id == project.company_id)).scalars().all()
    for msg in messages:
        entries.append(TimelineEntry(
            kind="message", title=f"{msg.sender_type.value} message",
            detail=msg.content[:120], timestamp=msg.created_at,
        ))

    entries.sort(key=lambda e: e.timestamp)
    return entries
