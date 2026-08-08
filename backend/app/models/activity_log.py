import uuid

from sqlalchemy import ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class ActivityLog(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "activity_logs"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    actor: Mapped[str] = mapped_column(String(150), nullable=False)  # student_id / manager / teammate name
    action: Mapped[str] = mapped_column(String(150), nullable=False)  # e.g. "task_started"
    detail: Mapped[str] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    __table_args__ = (
        Index("ix_activity_logs_company_id", "company_id"),
        Index("ix_activity_logs_action", "action"),
    )
