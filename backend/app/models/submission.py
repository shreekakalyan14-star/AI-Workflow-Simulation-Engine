import uuid
from datetime import datetime
from typing import List, Optional

from sqlalchemy import ARRAY, DateTime, Enum, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import (
    SubmissionStatus,
    ReviewStatus,
    ReviewResult,
    ReviewSeverity,
    FileType,
)


class Submission(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "submissions"

    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    student_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_status_enum"), nullable=False, default=SubmissionStatus.DRAFT
    )
    current_version: Mapped[int] = mapped_column(default=0, nullable=False)

    task = relationship("Task", back_populates="submissions")
    versions = relationship(
        "SubmissionVersion", back_populates="submission", cascade="all, delete-orphan", order_by="SubmissionVersion.version_number"
    )

    __table_args__ = (
        Index("ix_submissions_task_id", "task_id"),
        Index("ix_submissions_student_id", "student_id"),
        Index("ix_submissions_status", "status"),
    )


class SubmissionVersion(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "submission_versions"

    submission_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submissions.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(nullable=False)
    files: Mapped[List[dict]] = mapped_column(JSONB, nullable=False, default=list)
    version_metadata: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[SubmissionStatus] = mapped_column(
        Enum(SubmissionStatus, name="submission_version_status_enum"), nullable=False, default=SubmissionStatus.DRAFT
    )
    submitted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    submission = relationship("Submission", back_populates="versions")
    ai_reviews = relationship(
        "AIReview", back_populates="version", cascade="all, delete-orphan", order_by="AIReview.created_at"
    )

    __table_args__ = (
        Index("ix_submission_versions_submission_id", "submission_id"),
        Index("ix_submission_versions_version_number", "version_number"),
        Index("ix_submission_versions_status", "status"),
    )


class AIReview(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "ai_reviews"

    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("submission_versions.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="ai_review_status_enum"), nullable=False, default=ReviewStatus.PENDING
    )
    result: Mapped[ReviewResult] = mapped_column(
        Enum(ReviewResult, name="ai_review_result_enum"), nullable=False
    )
    severity: Mapped[ReviewSeverity] = mapped_column(
        Enum(ReviewSeverity, name="ai_review_severity_enum"), nullable=False
    )
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    risks: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    actions: Mapped[List[str]] = mapped_column(ARRAY(Text), nullable=False, default=list)
    score: Mapped[int] = mapped_column(nullable=False)
    raw_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    version = relationship("SubmissionVersion", back_populates="ai_reviews")
    history = relationship(
        "ReviewHistory", back_populates="review", cascade="all, delete-orphan", order_by="ReviewHistory.created_at"
    )

    __table_args__ = (
        Index("ix_ai_reviews_version_id", "version_id"),
        Index("ix_ai_reviews_status", "status"),
        Index("ix_ai_reviews_result", "result"),
    )


class ReviewHistory(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "review_history"

    review_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_reviews.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    previous_status: Mapped[Optional[ReviewStatus]] = mapped_column(
        Enum(ReviewStatus, name="review_history_prev_status_enum"), nullable=True
    )
    new_status: Mapped[ReviewStatus] = mapped_column(
        Enum(ReviewStatus, name="review_history_new_status_enum"), nullable=False
    )
    previous_result: Mapped[Optional[ReviewResult]] = mapped_column(
        Enum(ReviewResult, name="review_history_prev_result_enum"), nullable=True
    )
    new_result: Mapped[ReviewResult] = mapped_column(
        Enum(ReviewResult, name="review_history_new_result_enum"), nullable=False
    )
    changed_by: Mapped[str] = mapped_column(String(100), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload_snapshot: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    review = relationship("AIReview", back_populates="history")

    __table_args__ = (
        Index("ix_review_history_review_id", "review_id"),
        Index("ix_review_history_action", "action"),
    )