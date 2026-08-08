import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import SprintStatus


class SprintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    sprint_number: int
    name: str
    goal: str
    status: SprintStatus
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


class SprintWithTasks(SprintRead):
    tasks: List["TaskRead"] = []


from app.schemas.task import TaskRead  # noqa: E402

SprintWithTasks.model_rebuild()
