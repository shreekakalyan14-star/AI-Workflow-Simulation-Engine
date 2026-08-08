import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import CompanyType


class CompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    student_id: str
    name: str
    company_type: CompanyType
    industry: str
    department: str
    mission: str
    description: str
    created_at: datetime
    updated_at: datetime


class ManagerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    title: str
    personality: str
    satisfaction_score: int
