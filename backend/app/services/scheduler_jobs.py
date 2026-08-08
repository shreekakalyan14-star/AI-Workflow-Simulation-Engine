"""
Background jobs (APScheduler), satisfying the "APScheduler (background
events)" requirement with one real, useful job: periodically checking
every project's live ProjectState for high stress and pushing a manager
check-in notification when it crosses a threshold — driven by real state,
not a timer-only random event.
"""
import logging

from sqlalchemy import select

from app.core.database import SessionLocal
from app.models.enums import NotificationType
from app.models.project import Project
from app.models.project_state import ProjectState
from app.services.activity_log_service import log_activity
from app.services.notification_service import notify
from app.websockets.manager import manager as ws_manager

logger = logging.getLogger("aiwse.scheduler")

HIGH_STRESS_THRESHOLD = 80


async def check_high_stress_projects() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(ProjectState, Project)
            .join(Project, Project.id == ProjectState.project_id)
            .where(ProjectState.stress_level >= HIGH_STRESS_THRESHOLD)
        ).all()

        for state, project in rows:
            message = (
                f"Stress levels on '{project.title}' are high ({state.stress_level}/100). "
                "The manager is checking in — consider addressing blockers or missed deadlines."
            )
            notify(db, project.company_id, NotificationType.DEADLINE_UPDATED, message)
            log_activity(db, project.company_id, actor="system", action="scheduler:stress_checkin", detail=message)
            db.commit()

            await ws_manager.broadcast(
                str(project.company_id), "notification", {"message": message}
            )
    except Exception:
        logger.exception("check_high_stress_projects job failed")
        db.rollback()
    finally:
        db.close()
