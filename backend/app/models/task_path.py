import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import TaskStatus


class SimulationTaskPath(Base, UUIDPKMixin, TimestampMixin):
    """A student's personalized task path within a simulation.

    Each entry links a simulation to one canonical task with per-student status,
    allowing different students to have different subsets and orderings of tasks.
    """
    __tablename__ = "simulation_task_paths"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("simulations.id", ondelete="CASCADE"),
        nullable=False,
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[TaskStatus] = mapped_column(
        Enum(TaskStatus, name="task_status_enum", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=TaskStatus.BACKLOG,
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    simulation = relationship("Simulation", back_populates="task_paths")
    task = relationship("Task", back_populates="task_path_links")

    __table_args__ = (
        Index("ix_simulation_task_paths_simulation_id", "simulation_id"),
        Index("ix_simulation_task_paths_task_id", "task_id"),
        Index(
            "ix_simulation_task_paths_simulation_sequence",
            "simulation_id",
            "sequence",
            unique=True,
        ),
    )
