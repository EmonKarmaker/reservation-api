from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID


# ============== Chat Message Schemas ==============

class ChatMessageBase(BaseModel):
    """A single message in the conversation."""
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1)


class ChatMessageCreate(ChatMessageBase):
    """Message sent by user to the chatbot."""
    pass


class ChatMessageResponse(ChatMessageBase):
    """Message returned from API."""
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# ============== Conversation Schemas ==============

class ConversationStart(BaseModel):
    """Start a new conversation - needs business identifier."""
    business_slug: str = Field(..., min_length=1, max_length=120)
    user_session_id: str | None = Field(None, max_length=120)


class ConversationResponse(BaseModel):
    """Conversation info returned to client."""
    id: UUID
    business_id: UUID
    channel: str
    status: str
    outcome: str | None = None
    started_at: datetime
    last_message_at: datetime | None = None

    class Config:
        from_attributes = True


# ============== Chat Request/Response ==============

class ChatRequest(BaseModel):
    """User sending a message in existing conversation."""
    message: str = Field(..., min_length=1, max_length=2000)


class ChatResponse(BaseModel):
    """AI response to user message."""
    conversation_id: UUID
    message: str
    intent: str | None = None
    booking_id: UUID | None = None
    requires_action: str | None = None
    available_slots: list | None = None
    service_options: list | None = None


# ============== Handoff (Escalation) Schemas ==============

class HandoffRequest(BaseModel):
    """User requesting to talk to human."""
    reason: str = Field(..., min_length=1, max_length=80)
    contact_name: str = Field(..., min_length=1, max_length=120)
    contact_phone: str = Field(..., min_length=6, max_length=40)
    contact_email: str = Field(..., max_length=255)


class HandoffResponse(BaseModel):
    """Response after creating handoff request."""
    id: UUID
    public_ticket_id: str
    handoff_token: str
    status: str
    message: str = "A team member will contact you shortly."

    class Config:
        from_attributes = True


class HandoffStatusResponse(BaseModel):
    """Customer checking their escalation status."""
    public_ticket_id: str
    status: str
    reason: str
    created_at: datetime
    resolved_at: datetime | None = None