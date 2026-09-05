from __future__ import annotations

import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.enums import SubmissionStatus
from app.models.project import Project
from app.models.sprint import Sprint
from app.models.submission import SubmissionVersion
from app.models.task import Task
from app.services.ai.ai_service import AIService, get_ai_service
from app.services.ai.review_service import ReviewService

router = APIRouter(prefix="/api/projects/{project_id}/reviews", tags=["Reviews"])


def _get_owned_project(project_id: uuid.UUID, db: Session, user: CurrentUser) -> Project:
    project = db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    company = db.get(Company, project.company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your project")
    return project


def _get_owned_version(version_id: uuid.UUID, db: Session, user: CurrentUser) -> SubmissionVersion:
    version = db.get(SubmissionVersion, version_id)
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission version not found")
    
    task = db.get(Task, version.submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    project = db.get(Project, sprint.project_id)
    company = db.get(Company, project.company_id)
    
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your submission")
    return version


@router.post("/versions/{version_id}", status_code=status.HTTP_201_CREATED)
async def create_review(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    project = _get_owned_project(project_id, db, user)
    version = _get_owned_version(version_id, db, user)

    # Verify version belongs to this project
    task = db.get(Task, version.submission.task_id)
    sprint = db.get(Sprint, task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version does not belong to this project")

    # Only allow review of submitted versions
    if version.status != SubmissionStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Can only review submitted versions. Current status: {version.status.value}",
        )

    service = ReviewService(ai_service)
    return await service.review_submission_version(db, version)


@router.post("/versions/{version_id}/manager-review", status_code=status.HTTP_201_CREATED)
async def create_manager_review(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    project = _get_owned_project(project_id, db, user)
    version = _get_owned_version(version_id, db, user)

    sprint = db.get(Sprint, version.submission.task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version does not belong to this project")

    # Only allow manager review after AI review (version should be in a reviewed state)
    if version.status not in (SubmissionStatus.APPROVED, SubmissionStatus.CHANGES_REQUESTED, SubmissionStatus.REJECTED):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Manager review requires completed AI review. Current status: {version.status.value}",
        )

    service = ReviewService(ai_service)
    return await service.review_by_manager(db, version)


@router.get("/versions/{version_id}/history", response_model=List[Dict[str, Any]])
def get_review_history(
    project_id: uuid.UUID,
    version_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    project = _get_owned_project(project_id, db, user)
    version = _get_owned_version(version_id, db, user)

    sprint = db.get(Sprint, version.submission.task.sprint_id)
    if sprint.project_id != project.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version does not belong to this project")

    service = ReviewService(ai_service)
    return service.get_review_history(db, version_id)