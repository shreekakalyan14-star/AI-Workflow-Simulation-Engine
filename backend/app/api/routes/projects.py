import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.project import Project
from app.models.project_state import ProjectState
from app.schemas.project import ProjectRead, ProjectStateRead

router = APIRouter(prefix="/api/projects", tags=["Projects"])


def _get_owned_project(
    project_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return project


@router.get("", response_model=List[ProjectRead])
def list_my_projects(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = (
        select(Project)
        .join(Company, Company.id == Project.company_id)
        .where(Company.student_id == user.student_id)
        .order_by(Project.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@router.get("/{project_id}", response_model=ProjectRead)
def get_project(project: Project = Depends(_get_owned_project)):
    return project


@router.get("/{project_id}/state", response_model=ProjectStateRead)
def get_project_state(
    project: Project = Depends(_get_owned_project),
    db: Session = Depends(get_db),
):
    stmt = select(ProjectState).where(ProjectState.project_id == project.id)
    state = db.execute(stmt).scalar_one_or_none()
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project state not found")
    return state
