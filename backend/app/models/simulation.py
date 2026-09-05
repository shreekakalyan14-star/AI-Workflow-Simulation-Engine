import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import (
    DifficultyLevel,
    ScenarioStatus,
    SimulationStatus,
    TaskType,
    WorkflowEventType,
)


class Simulation(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "simulations"

    student_id: Mapped[str] = mapped_column(String(100), nullable=False)
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )

    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, name="difficulty_level_enum"), nullable=False
    )
    duration_weeks: Mapped[int] = mapped_column(Integer, nullable=False, default=4)

    status: Mapped[SimulationStatus] = mapped_column(
        Enum(SimulationStatus, name="simulation_status_enum"), nullable=False, default=SimulationStatus.NOT_STARTED
    )

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    current_scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)
    current_task_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), nullable=True)

    progress: Mapped[int] = mapped_column(default=0, nullable=False)

    company = relationship("Company", back_populates="simulations")
    project = relationship("Project", back_populates="simulations")
    task_paths = relationship(
        "SimulationTaskPath",
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="SimulationTaskPath.sequence",
    )
    scenarios = relationship(
        "Scenario",
        back_populates="simulation",
        cascade="all, delete-orphan",
        order_by="Scenario.sequence",
        foreign_keys="Scenario.simulation_id",
    )
    current_scenario = relationship(
        "Scenario",
        foreign_keys=[current_scenario_id],
        primaryjoin="Simulation.current_scenario_id == Scenario.id",
        uselist=False,
    )
    current_task = relationship(
        "Task",
        foreign_keys=[current_task_id],
        primaryjoin="Simulation.current_task_id == Task.id",
        uselist=False,
    )

    __table_args__ = (
        Index("ix_simulations_student_id", "student_id"),
        Index("ix_simulations_company_id", "company_id"),
        Index("ix_simulations_project_id", "project_id"),
        Index("ix_simulations_status", "status"),
    )


class Scenario(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "scenarios"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False
    )

    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    workplace_context: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str] = mapped_column(String(100), nullable=False)
    difficulty: Mapped[DifficultyLevel] = mapped_column(
        Enum(DifficultyLevel, name="difficulty_level_enum"), nullable=False
    )
    required_skills: Mapped[List[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    objectives: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)

    status: Mapped[ScenarioStatus] = mapped_column(
        Enum(ScenarioStatus, name="scenario_status_enum"), nullable=False, default=ScenarioStatus.PENDING
    )

    sequence_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    simulation = relationship("Simulation", back_populates="scenarios", foreign_keys=[simulation_id])
    tasks = relationship("ScenarioTask", back_populates="scenario", cascade="all, delete-orphan", order_by="ScenarioTask.sequence")

    __table_args__ = (
        Index("ix_scenarios_simulation_id", "simulation_id"),
        Index("ix_scenarios_status", "status"),
        Index("ix_scenarios_sequence", "simulation_id", "sequence", unique=True),
    )


class ScenarioTask(Base, UUIDPKMixin, TimestampMixin):
    """Links tasks to scenarios with additional scenario-specific metadata."""
    __tablename__ = "scenario_tasks"

    scenario_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)

    scenario = relationship("Scenario", back_populates="tasks")
    task = relationship("Task", back_populates="scenario_links")

    __table_args__ = (
        Index("ix_scenario_tasks_scenario_id", "scenario_id"),
        Index("ix_scenario_tasks_task_id", "task_id"),
        Index("ix_scenario_tasks_sequence", "scenario_id", "sequence", unique=True),
    )


class WorkflowEvent(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "workflow_events"

    simulation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("simulations.id", ondelete="CASCADE"), nullable=False
    )
    task_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL"), nullable=True
    )
    scenario_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenarios.id", ondelete="SET NULL"), nullable=True
    )

    event_type: Mapped[WorkflowEventType] = mapped_column(
        Enum(WorkflowEventType, name="workflow_event_type_enum"), nullable=False
    )
    title: Mapped[str] = mapped_column(String(250), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # Original and updated requirements for REQUIREMENT_CHANGE events
    original_requirement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_requirement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    trigger_condition: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    action_required: Mapped[bool] = mapped_column(default=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="pending")
    response: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    simulation = relationship("Simulation", foreign_keys=[simulation_id])
    task = relationship("Task", foreign_keys=[task_id])
    scenario = relationship("Scenario", foreign_keys=[scenario_id])

    __table_args__ = (
        Index("ix_workflow_events_simulation_id", "simulation_id"),
        Index("ix_workflow_events_task_id", "task_id"),
        Index("ix_workflow_events_type", "event_type"),
        Index("ix_workflow_events_occurred_at", "occurred_at"),
        Index("ix_workflow_events_status", "status"),
    )