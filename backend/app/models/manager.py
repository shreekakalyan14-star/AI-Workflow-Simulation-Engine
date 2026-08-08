import uuid

from sqlalchemy import Enum, ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import ManagerPersonality


class Manager(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "managers"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    personality: Mapped[ManagerPersonality] = mapped_column(
        Enum(ManagerPersonality, name="manager_personality_enum"), nullable=False
    )

    # Manager mood/satisfaction is state, not static data — see ProjectState too,
    # but we keep a live convenience copy here for quick UI reads.
    satisfaction_score: Mapped[int] = mapped_column(default=70, nullable=False)

    company = relationship("Company", back_populates="manager")

    __table_args__ = (
        Index("ix_managers_company_id", "company_id"),
    )
