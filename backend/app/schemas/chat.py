import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import MessageSenderType


class ChatMessageCreate(BaseModel):
    content: str = Field(..., min_length=1)


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company_id: uuid.UUID
    sender_type: MessageSenderType
    sender_id: str
    content: str
    created_at: datetime


class ChatExchange(BaseModel):
    """Returned after posting a chat message: the student's message + the AI reply."""
    student_message: MessageRead
    reply: MessageRead
