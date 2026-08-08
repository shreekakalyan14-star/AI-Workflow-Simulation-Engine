"""FEATURE 7 (read side): list a company's AI teammates."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.team_member import TeamMember
from app.schemas.team import TeamMemberRead

router = APIRouter(prefix="/api/companies/{company_id}/team", tags=["Team"])


@router.get("", response_model=List[TeamMemberRead])
def list_team_members(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    company = db.get(Company, company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your company")
    stmt = select(TeamMember).where(TeamMember.company_id == company_id)
    return db.execute(stmt).scalars().all()
