import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Integer, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB, TSVECTOR

from app.core.database import Base


class CallSession(Base):
    """Voice call sessions with full transcript and search capabilities."""
    __tablename__ = "call_sessions"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    
    # Unique identifiers
    public_call_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    provider_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    
    # Caller info
    caller_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    caller_country: Mapped[str | None] = mapped_column(String(10), nullable=True)
    
    # Call info
    channel: Mapped[str] = mapped_column(String(20), default="VOICE")
    status: Mapped[str] = mapped_column(
        Enum('IN_PROGRESS', 'COMPLETED', 'ESCALATED', 'ABANDONED', 'FAILED',
             name='call_status_enum', schema='core', create_type=False),
        default="IN_PROGRESS"
    )
    
    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # AI metrics
    total_ai_messages: Mapped[int] = mapped_column(Integer, default=0)
    total_user_messages: Mapped[int] = mapped_column(Integer, default=0)
    
    # Resolution
    resolution_type: Mapped[str | None] = mapped_column(
        Enum('AI_RESOLVED', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'TECHNICAL_FAILURE', 'TRANSFERRED',
             name='call_resolution_enum', schema='core', create_type=False),
        nullable=True
    )
    outcome: Mapped[str | None] = mapped_column(
        Enum('BOOKING_CREATED', 'BOOKING_CANCELLED', 'BOOKING_RESCHEDULED', 'STATUS_PROVIDED',
             'INFO_PROVIDED', 'ESCALATED_TO_HUMAN', 'NO_ACTION', 'FAILED',
             name='call_outcome_enum', schema='core', create_type=False),
        nullable=True
    )
    
    # Linked records
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.conversations.id"), nullable=True)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.bookings.id"), nullable=True)
    handoff_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.handoff_requests.id"), nullable=True)
    
    # Searchable transcript
    full_transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    transcript_search: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    
    # Extra data (renamed from metadata which is reserved)
    extra_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    business = relationship("Business", back_populates="call_sessions")
    conversation = relationship("Conversation", back_populates="call_session")
    booking = relationship("Booking", back_populates="call_session")
    handoff = relationship("HandoffRequest", back_populates="call_session")