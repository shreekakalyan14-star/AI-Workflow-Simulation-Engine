import uuid

from sqlalchemy import Float, ForeignKey, Index, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class ProjectState(Base, UUIDPKMixin, TimestampMixin):
    """
    Single source of truth for the stateful workflow engine.
    One row per project. Every event/task action reads and mutates this row,
    and future AI decisions (manager mood, event triggers, difficulty ramps)
    are derived from it rather than from randomness.
    """

    __tablename__ = "project_states"

    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    completed_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    pending_tasks: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    avg_completion_time_hours: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    missed_deadlines: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    bug_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    communication_frequency: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # msgs/day
    stress_level: Mapped[int] = mapped_column(Integer, nullable=False, default=20)  # 0-100
    manager_satisfaction: Mapped[int] = mapped_column(Integer, nullable=False, default=70)  # 0-100
    team_satisfaction: Mapped[int] = mapped_column(Integer, nullable=False, default=70)  # 0-100
    current_sprint_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    project = relationship("Project", back_populates="project_state")

    __table_args__ = (
        Index("ix_project_states_project_id", "project_id"),
    )
