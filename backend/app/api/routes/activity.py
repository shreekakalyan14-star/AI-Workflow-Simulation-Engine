"""FEATURE 13: Activity Log."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.activity_log import ActivityLog
from app.models.company import Company
from app.schemas.misc import ActivityLogRead

router = APIRouter(prefix="/api/companies/{company_id}/activity", tags=["Activity Log"])


@router.get("", response_model=List[ActivityLogRead])
def list_activity(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    company = db.get(Company, company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your company")
    stmt = (
        select(ActivityLog)
        .where(ActivityLog.company_id == company_id)
        .order_by(ActivityLog.created_at.desc())
        .limit(200)
    )
    return db.execute(stmt).scalars().all()
