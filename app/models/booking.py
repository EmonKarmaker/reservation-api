import uuid
from datetime import datetime
from sqlalchemy import String, Text, DateTime, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.conversations.id"), nullable=True)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.services.id"), nullable=False)
    public_tracking_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(
        Enum(
            'INITIATED', 'SLOT_SELECTED', 'CONTACT_COLLECTED', 'PAYMENT_PENDING',
            'CONFIRMED', 'CANCELLED', 'FAILED', 'HUMAN_HANDOFF', 'PENDING_PAYMENT',
            'CANCELED', 'RESCHEDULED', 'EXPIRED',
            name='booking_status_enum', schema='core', create_type=False
        ),
        default="INITIATED"
    )
    resolution_type: Mapped[str | None] = mapped_column(
        Enum(
            'AI_RESOLVED', 'HUMAN_HANDOFF', 'HUMAN_ESCALATED', 'USER_ABANDONED', 'FAILED', 'CALL_REQUESTED',
            name='resolution_type_enum', schema='core', create_type=False
        ),
        nullable=True
    )
    slot_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    slot_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customer_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    customer_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    customer_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    contact_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    payment_status: Mapped[str] = mapped_column(
        Enum(
            'CREATED', 'PENDING', 'PAID', 'FAILED', 'EXPIRED', 'REFUNDED',
            name='payment_status_enum', schema='core', create_type=False
        ),
        default="CREATED"
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    business = relationship("Business", back_populates="bookings")
    service = relationship("Service", back_populates="bookings")
    call_session = relationship("CallSession", back_populates="booking", uselist=False)
    conversation = relationship("Conversation", back_populates="bookings")
    payment_sessions = relationship("PaymentSession", back_populates="booking")
    status_history = relationship("BookingStatusHistory", back_populates="booking")
    handoff_requests = relationship("HandoffRequest", back_populates="booking")