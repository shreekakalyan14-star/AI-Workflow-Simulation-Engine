import uuid
from typing import List

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_owned_company
from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.schemas.company import CompanyRead, ManagerRead

router = APIRouter(prefix="/api/companies", tags=["Companies"])


@router.get("", response_model=List[CompanyRead])
def list_my_companies(
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    stmt = select(Company).where(Company.student_id == user.student_id).order_by(Company.created_at.desc())
    return db.execute(stmt).scalars().all()


@router.get("/{company_id}", response_model=CompanyRead)
def get_company(company: Company = Depends(get_owned_company)):
    return company


@router.get("/{company_id}/manager", response_model=ManagerRead)
def get_company_manager(company: Company = Depends(get_owned_company)):
    return company.manager
