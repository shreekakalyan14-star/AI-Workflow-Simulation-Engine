import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import DifficultyLevel, ProjectStatus


class Project(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "projects"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    technology_stack: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, name="difficulty_level_enum"), nullable=False
    )
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status_enum"),
        nullable=False,
        default=ProjectStatus.PLANNING,
    )

    objectives: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    modules: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    deliverables: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    company = relationship("Company", back_populates="projects")
    sprints = relationship(
        "Sprint", back_populates="project", cascade="all, delete-orphan", order_by="Sprint.sprint_number"
    )
    project_state = relationship(
        "ProjectState", back_populates="project", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_projects_company_id", "company_id"),
        Index("ix_projects_status", "status"),
    )
