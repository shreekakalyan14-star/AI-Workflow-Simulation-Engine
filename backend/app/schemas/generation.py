import uuid
from typing import List

from pydantic import BaseModel, Field

from app.models.enums import CompanyType, DifficultyLevel


class GenerationRequest(BaseModel):
    """
    The input contract for FEATURE 1-3: given these five fields, the engine
    generates a full company + project + sprint/task breakdown.
    """

    student_id: str = Field(..., min_length=1)
    role: str = Field(..., examples=["Backend Developer", "AI Engineer", "Cybersecurity"])
    technology_stack: List[str] = Field(..., min_length=1, examples=[["Python", "FastAPI", "PostgreSQL"]])
    difficulty: DifficultyLevel
    company_type: CompanyType


class GenerationResponse(BaseModel):
    company_id: uuid.UUID
    project_id: uuid.UUID
    sprint_ids: List[uuid.UUID]
    task_count: int
