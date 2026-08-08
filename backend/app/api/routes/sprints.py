import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.project import Project
from app.models.sprint import Sprint
from app.schemas.sprint import SprintRead, SprintWithTasks

router = APIRouter(prefix="/api/projects/{project_id}/sprints", tags=["Sprints"])


def _assert_project_owned(project_id: uuid.UUID, db: Session, user: CurrentUser) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return project


@router.get("", response_model=List[SprintRead])
def list_sprints(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _assert_project_owned(project_id, db, user)
    stmt = select(Sprint).where(Sprint.project_id == project_id).order_by(Sprint.sprint_number)
    return db.execute(stmt).scalars().all()


@router.get("/{sprint_id}", response_model=SprintWithTasks)
def get_sprint(
    project_id: uuid.UUID,
    sprint_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _assert_project_owned(project_id, db, user)
    stmt = (
        select(Sprint)
        .options(selectinload(Sprint.tasks))
        .where(Sprint.id == sprint_id, Sprint.project_id == project_id)
    )
    sprint = db.execute(stmt).scalar_one_or_none()
    if sprint is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sprint not found")
    return sprint
