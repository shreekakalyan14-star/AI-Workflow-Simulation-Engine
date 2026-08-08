import uuid

from sqlalchemy import Enum, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPKMixin
from app.models.enums import MessageSenderType


class Message(Base, UUIDPKMixin, TimestampMixin):
    __tablename__ = "messages"

    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False
    )
    sender_type: Mapped[MessageSenderType] = mapped_column(
        Enum(MessageSenderType, name="message_sender_type_enum"), nullable=False
    )
    sender_id: Mapped[str] = mapped_column(Text, nullable=False)  # student_id, manager.id, or team_member.id
    content: Mapped[str] = mapped_column(Text, nullable=False)

    __table_args__ = (
        Index("ix_messages_company_id", "company_id"),
        Index("ix_messages_created_at", "created_at"),
    )
