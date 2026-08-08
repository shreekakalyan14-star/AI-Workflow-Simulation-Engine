import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import SprintStatus


class Sprint(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "sprints"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    sprint_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    goal: Mapped[str] = mapped_column(String(500), nullable=False)
    status: Mapped[SprintStatus] = mapped_column(
        Enum(SprintStatus, name="sprint_status_enum"), nullable=False, default=SprintStatus.PLANNED
    )

    start_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    project = relationship("Project", back_populates="sprints")
    tasks = relationship("Task", back_populates="sprint", cascade="all, delete-orphan")
    sprint_review = relationship(
        "SprintReview", back_populates="sprint", uselist=False, cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_sprints_project_id", "project_id"),
        Index("ix_sprints_project_sprint_number", "project_id", "sprint_number", unique=True),
    )
