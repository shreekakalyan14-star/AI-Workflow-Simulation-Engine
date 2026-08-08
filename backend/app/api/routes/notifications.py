"""FEATURE 12: Notifications."""
import uuid
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.models.company import Company
from app.models.notification import Notification
from app.schemas.misc import NotificationRead

router = APIRouter(prefix="/api/companies/{company_id}/notifications", tags=["Notifications"])


def _owned_company(company_id, db, user):
    company = db.get(Company, company_id)
    if company is None or company.student_id != user.student_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your company")
    return company


@router.get("", response_model=List[NotificationRead])
def list_notifications(
    company_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _owned_company(company_id, db, user)
    stmt = (
        select(Notification)
        .where(Notification.company_id == company_id)
        .order_by(Notification.created_at.desc())
    )
    return db.execute(stmt).scalars().all()


@router.patch("/{notification_id}/read", response_model=NotificationRead)
def mark_notification_read(
    company_id: uuid.UUID,
    notification_id: uuid.UUID,
    db: Session = Depends(get_db),
    user: CurrentUser = Depends(get_current_user),
):
    _owned_company(company_id, db, user)
    notif = db.get(Notification, notification_id)
    if notif is None or notif.company_id != company_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notif.is_read = True
    db.add(notif)
    db.commit()
    db.refresh(notif)
    return notif
