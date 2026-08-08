from __future__ import annotations

import uuid
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.project import Project
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_review(
    project_id: uuid.UUID,
    payload: Dict[str, Any],
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
    ai_service: AIService = Depends(get_ai_service),
):
    project = _get_owned_project(project_id, db, user)
    service = ReviewService(ai_service)
    return await service.review_submission(db, project, submission_payload=payload)
