"""FEATURE 12: Notifications — a thin, reused-everywhere creation helper."""
from sqlalchemy.orm import Session

from app.models.enums import NotificationType
from app.models.notification import Notification


def notify(db: Session, company_id, notification_type: NotificationType, message: str) -> Notification:
    n = Notification(company_id=company_id, notification_type=notification_type, message=message)
    db.add(n)
    db.flush()
    return n
