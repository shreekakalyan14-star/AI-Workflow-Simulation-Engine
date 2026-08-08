import uuid
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict

from app.models.enums import DifficultyLevel, ProjectStatus


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    title: str
    role: str
    technology_stack: List[str]
    difficulty: DifficultyLevel
    status: ProjectStatus
    objectives: List[str]
    modules: List[str]
    deliverables: List[str]
    duration_weeks: int
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class ProjectStateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: uuid.UUID
    completed_tasks: int
    pending_tasks: int
    avg_completion_time_hours: float
    missed_deadlines: int
    bug_count: int
    communication_frequency: int
    stress_level: int
    manager_satisfaction: int
    team_satisfaction: int
    current_sprint_number: int
