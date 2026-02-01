import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Conversation(Base):
    __tablename__ = "conversations"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    channel: Mapped[str] = mapped_column(
        Enum('CHAT', 'VOICE', 'HUMAN', name='conversation_channel_enum', schema='core', create_type=False),
        nullable=False
    )
    status: Mapped[str] = mapped_column(
        Enum('STARTED', 'IN_PROGRESS', 'RESOLVED', 'ABANDONED', name='conversation_status_enum', schema='core', create_type=False),
        default="STARTED"
    )
    resolution_type: Mapped[str | None] = mapped_column(
        Enum('AI_RESOLVED', 'HUMAN_HANDOFF', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'FAILED', 'CALL_REQUESTED', name='resolution_type_enum', schema='core', create_type=False),
        nullable=True
    )
    outcome: Mapped[str | None] = mapped_column(
        Enum('BOOKED', 'ESCALATED', 'DROPPED', name='conversation_outcome_enum', schema='core', create_type=False),
        nullable=True
    )
    user_session_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_activity_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    business = relationship("Business", back_populates="conversations")
    messages = relationship("ConversationMessage", back_populates="conversation")
    call_session = relationship("CallSession", back_populates="conversation", uselist=False)
    bookings = relationship("Booking", back_populates="conversation")
    handoff_requests = relationship("HandoffRequest", back_populates="conversation")