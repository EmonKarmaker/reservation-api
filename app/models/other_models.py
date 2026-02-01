import uuid
from datetime import datetime, time
from decimal import Decimal
from sqlalchemy import String, Text, DateTime, ForeignKey, Numeric, Boolean, Integer, Enum, SmallInteger, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from app.core.database import Base


class AdminUser(Base):
    """Admin users who manage businesses and handle escalations."""
    __tablename__ = "admin_users"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(String(40), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    assigned_handoffs = relationship("HandoffRequest", back_populates="assigned_admin")


class BusinessOperatingHours(Base):
    """Weekly operating hours for each business. One row per day (0=Monday to 6=Sunday)."""
    __tablename__ = "business_operating_hours"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    day_of_week: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    open_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    close_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="operating_hours")


class BusinessAISettings(Base):
    """AI chatbot configuration for each business - personality, permissions, thresholds."""
    __tablename__ = "business_ai_settings"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), unique=True, nullable=False)
    agent_name: Mapped[str] = mapped_column(String(120), nullable=False)
    tone_of_voice: Mapped[str | None] = mapped_column(String(120), nullable=True)
    personality: Mapped[str | None] = mapped_column(Text, nullable=True)
    business_display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_ai_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    fallback_to_human: Mapped[bool] = mapped_column(Boolean, default=True)
    voice_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    confidence_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=0.650)
    allow_cancel_bookings: Mapped[bool] = mapped_column(Boolean, default=False)
    allow_reschedule_bookings: Mapped[bool] = mapped_column(Boolean, default=False)
    mention_promotions: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="ai_settings")
    welcome_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    max_retries: Mapped[int | None] = mapped_column(Integer, nullable=True)
    language: Mapped[str | None] = mapped_column(String(10), nullable=True)


class BusinessNotificationSettings(Base):
    """Notification channel toggles for each business."""
    __tablename__ = "business_notification_settings"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), unique=True, nullable=False)
    email_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    whatsapp_alerts_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    business = relationship("Business", back_populates="notification_settings")


class BusinessAvailabilityException(Base):
    __tablename__ = "business_availability_exceptions"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    exception_type: Mapped[str] = mapped_column(
        Enum('CLOSED', 'MODIFIED_HOURS', 'SPECIAL_EVENT', name='availability_exception_type_enum', schema='core', create_type=False),
        nullable=False
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    business = relationship("Business", back_populates="availability_exceptions")

class ServiceImage(Base):
    """Images for services - shown when user asks for service details."""
    __tablename__ = "service_images"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.services.id"), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    alt_text: Mapped[str | None] = mapped_column(String(200), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    service = relationship("Service", back_populates="images")


class ServiceCapacityRule(Base):
    """How many bookings a service can have per time slot."""
    __tablename__ = "service_capacity_rules"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    service_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.services.id"), unique=True, nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    slot_length_minutes: Mapped[int] = mapped_column(Integer, default=30)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    service = relationship("Service", back_populates="capacity_rule")


class HandoffRequest(Base):
    """Human escalation requests - when AI can't help or user wants human."""
    __tablename__ = "handoff_requests"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.conversations.id"), nullable=False)
    booking_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.bookings.id"), nullable=True)
    status: Mapped[str] = mapped_column(
        Enum('OPEN', 'ASSIGNED', 'RESOLVED', 'CLOSED', name='handoff_status_enum', schema='core', create_type=False),
        default="OPEN"
    )
    reason: Mapped[str] = mapped_column(String(80), nullable=False)
    contact_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    assigned_to_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.admin_users.id"), nullable=True)
    public_ticket_id: Mapped[str | None] = mapped_column(String(24), unique=True, nullable=True)
    handoff_token: Mapped[str | None] = mapped_column(String(80), unique=True, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    business = relationship("Business", back_populates="handoff_requests")
    call_session=relationship("CallSession",back_populates="handoff", uselist=False)
    conversation = relationship("Conversation", back_populates="handoff_requests")
    booking = relationship("Booking", back_populates="handoff_requests")
    assigned_admin = relationship("AdminUser", back_populates="assigned_handoffs")


class BookingStatusHistory(Base):
    """Audit trail - logs every booking status change with who changed it and why."""
    __tablename__ = "booking_status_history"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.bookings.id"), nullable=False)
    old_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    new_status: Mapped[str] = mapped_column(String(30), nullable=False)
    changed_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.admin_users.id"), nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    booking = relationship("Booking", back_populates="status_history")


class PaymentSession(Base):
    """Payment gateway sessions - tracks payment attempts for each booking."""
    __tablename__ = "payment_sessions"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.businesses.id"), nullable=False)
    booking_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("core.bookings.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_session_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="CREATED")
    payment_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    booking = relationship("Booking", back_populates="payment_sessions")


class PaymentEvent(Base):
    """Webhook events from payment providers - raw event log for debugging and reconciliation."""
    __tablename__ = "payment_events"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    business_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    provider: Mapped[str] = mapped_column(String(30), nullable=False)
    provider_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    event_type: Mapped[str] = mapped_column(String(120), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)