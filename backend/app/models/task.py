import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ARRAY, DateTime, Enum, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import DifficultyLevel, TaskPriority, TaskStatus, TaskType


class Task(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "tasks"

    sprint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("sprints.id", ondelete="CASCADE"), nullable=False
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    acceptance_criteria: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    priority: Mapped[TaskPriority] = mapped_column(
        Enum(TaskPriority, name="task_priority_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=TaskPriority.MEDIUM
    )
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=TaskStatus.BACKLOG
    )

    task_type: Mapped[TaskType] = mapped_column(
        Enum(TaskType, name="task_type_enum", values_callable=lambda x: [e.value for e in x]), nullable=False, default=TaskType.CODING
    )

    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, name="difficulty_level_enum"), nullable=False, default=DifficultyLevel.INTERMEDIATE
    )

    estimated_hours: Mapped[float] = mapped_column(Float, nullable=False, default=4.0)
    deadline: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    blocked_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    deliverable_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    sprint = relationship("Sprint", back_populates="tasks")
    task_path_links = relationship("SimulationTaskPath", back_populates="task")
    dependencies = relationship(
        "TaskDependency",
        foreign_keys="TaskDependency.task_id",
        back_populates="task",
        cascade="all, delete-orphan",
    )
    submissions = relationship("Submission", back_populates="task", cascade="all, delete-orphan")
    scenario_links = relationship("ScenarioTask", back_populates="task", cascade="all, delete-orphan")

    __table_args__ = (
        Index("ix_tasks_sprint_id", "sprint_id"),
        Index("ix_tasks_status", "status"),
        Index("ix_tasks_priority", "priority"),
        Index("ix_tasks_deadline", "deadline"),
        Index("ix_tasks_sprint_sequence", "sprint_id", "sequence"),
    )


class TaskDependency(Base, UUIDPKMixin, TimestampMixin):
    """task_id depends on depends_on_task_id (must complete first)."""

    __tablename__ = "task_dependencies"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )

    task = relationship("Task", foreign_keys=[task_id], back_populates="dependencies")

    __table_args__ = (
        Index("ix_task_dependencies_task_id", "task_id"),
        Index("ix_task_dependencies_depends_on_task_id", "depends_on_task_id"),
        Index("ix_task_dependencies_unique_pair", "task_id", "depends_on_task_id", unique=True),
    )
