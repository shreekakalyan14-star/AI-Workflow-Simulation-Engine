"""FEATURE 10: Meetings."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.meeting import MeetingSchedule
from app.models.project import Project
from app.schemas.misc import MeetingComplete, MeetingRead
from app.services.activity_log_service import log_activity

router = APIRouter(prefix="/api/projects/{project_id}/meetings", tags=["Meetings"])


def _owned_project(project_id, db, user) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return project


@router.get("", response_model=List[MeetingRead])
def list_meetings(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _owned_project(project_id, db, user)
    stmt = (
        select(MeetingSchedule)
        .where(MeetingSchedule.project_id == project_id)
        .order_by(MeetingSchedule.scheduled_at)
    )
    return db.execute(stmt).scalars().all()


@router.patch("/{meeting_id}/complete", response_model=MeetingRead)
def complete_meeting(
    project_id: uuid.UUID,
    meeting_id: uuid.UUID,
    payload: MeetingComplete,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    project = _owned_project(project_id, db, user)
    meeting = db.get(MeetingSchedule, meeting_id)
    if meeting is None or meeting.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Meeting not found")

    meeting.completed = True
    meeting.notes = payload.notes
    meeting.attendance = payload.attendance
    meeting.action_items = payload.action_items
    db.add(meeting)
    log_activity(
        db, project.company_id, actor=user.student_id, action="meeting:completed",
        detail=meeting.agenda,
    )
    db.commit()
    db.refresh(meeting)
    return meeting
