"""FEATURE 9: Dynamic Events Engine — read + manual-trigger (for demo/testing/instructor tooling)."""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.enums import EventType
from app.models.event import Event
from app.models.project import Project
from app.models.project_state import ProjectState
from app.schemas.misc import EventRead
from app.services.engines.events_engine import trigger_event

router = APIRouter(prefix="/api/projects/{project_id}/events", tags=["Events"])


def _owned_project(project_id, db, user) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return project


@router.get("", response_model=List[EventRead])
def list_events(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _owned_project(project_id, db, user)
    stmt = select(Event).where(Event.project_id == project_id).order_by(Event.created_at.desc())
    return db.execute(stmt).scalars().all()


class TriggerEventRequest(BaseModel):
    event_type: EventType
    description: Optional[str] = None


@router.post("/trigger", response_model=EventRead, status_code=status.HTTP_201_CREATED)
async def manually_trigger_event(
    project_id: uuid.UUID,
    payload: TriggerEventRequest,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    """
    Manually fire a dynamic event — useful for demoing/testing FEATURE 9
    without waiting for the automatic triggers in workflow_engine.py to
    fire, and a natural hook for future instructor/admin tooling.
    """
    project = _owned_project(project_id, db, user)
    description = payload.description or f"A {payload.event_type.value.replace('_', ' ')} occurred."
    event = await trigger_event(db, project, payload.event_type, description)
    db.commit()
    db.refresh(event)
    return event
