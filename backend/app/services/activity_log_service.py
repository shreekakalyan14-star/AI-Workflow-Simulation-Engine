"""FEATURE 13: Activity Log — a thin, reused-everywhere logging helper."""
from typing import Optional

from sqlalchemy.orm import Session

from app.models.activity_log import ActivityLog


def log_activity(
    db: Session, company_id, actor: str, action: str, detail: Optional[str] = None, **metadata
) -> ActivityLog:
    entry = ActivityLog(
        company_id=company_id, actor=actor, action=action, detail=detail, metadata_json=metadata
    )
    db.add(entry)
    db.flush()
    return entry
