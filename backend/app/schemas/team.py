import uuid

from pydantic import BaseModel, ConfigDict


class TeamMemberRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    name: str
    role: str
    personality: str
    skill_level: int
