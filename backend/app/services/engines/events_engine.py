"""
FEATURE 9: Dynamic Events Engine.

A single entry point (`trigger_event`) that any part of the system calls
to raise a real event: it persists the Event row, creates a Notification,
logs an ActivityLog entry, and pushes a live update over WebSocket to
anyone watching that company. Callers decide *when* to call this based on
real project state (see workflow_engine.py) — this module never invents
events on its own.
"""
from app.models.enums import EventType, NotificationType
from app.models.event import Event
from app.services.activity_log_service import log_activity
from app.services.notification_service import notify
from app.websockets.manager import manager as ws_manager

_EVENT_NOTIFICATION_TYPE = {
    EventType.DEADLINE_CHANGED: NotificationType.DEADLINE_UPDATED,
    EventType.BUG_REPORT: NotificationType.BUG_REPORTED,
}


async def trigger_event(db, project, event_type: EventType, description: str, payload: dict | None = None):
    payload = payload or {}
    event = Event(project_id=project.id, event_type=event_type, description=description, payload=payload)
    db.add(event)
    db.flush()

    notification_type = _EVENT_NOTIFICATION_TYPE.get(event_type, NotificationType.REQUIREMENT_CHANGED)
    notify(db, project.company_id, notification_type, description)
    log_activity(db, project.company_id, actor="system", action=f"event:{event_type.value}", detail=description)

    await ws_manager.broadcast(
        str(project.company_id),
        "event",
        {"event_type": event_type.value, "description": description, "project_id": str(project.id)},
    )
    return event
