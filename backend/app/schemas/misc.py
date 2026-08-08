"""Read schemas for Notification, Event, ActivityLog, MeetingSchedule — the Phase 3 read surfaces."""
import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import EventType, MeetingType, NotificationType


class NotificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    notification_type: NotificationType
    message: str
    is_read: bool
    created_at: datetime


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    event_type: EventType
    description: str
    payload: dict
    created_at: datetime


class ActivityLogRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    company_id: uuid.UUID
    actor: str
    action: str
    detail: Optional[str] = None
    created_at: datetime


class MeetingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    project_id: uuid.UUID
    meeting_type: MeetingType
    scheduled_at: Optional[datetime] = None
    agenda: str
    participants: List[str]
    notes: Optional[str] = None
    attendance: List[str]
    action_items: List[str]
    completed: bool


class MeetingComplete(BaseModel):
    notes: Optional[str] = None
    attendance: List[str] = []
    action_items: List[str] = []


class TimelineEntry(BaseModel):
    kind: str  # "task_completed" | "event" | "meeting" | "message"
    title: str
    detail: Optional[str] = None
    timestamp: datetime
