import uuid

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin


class TeamMember(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "team_members"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    role: Mapped[str] = mapped_column(String(150), nullable=False)
    personality: Mapped[str] = mapped_column(String(100), nullable=False)
    skill_level: Mapped[int] = mapped_column(Integer, nullable=False, default=50)  # 0-100

    company = relationship("Company", back_populates="team_members")

    __table_args__ = (
        Index("ix_team_members_company_id", "company_id"),
    )
