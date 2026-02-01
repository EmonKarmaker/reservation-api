import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Business(Base):
    __tablename__ = "businesses"
    __table_args__ = {"schema": "core"}

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    business_name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(50), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE")
    created_by_admin_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("core.admin_users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    # Relationships
    services = relationship("Service", back_populates="business")
    call_sessions = relationship("CallSession", back_populates="business")
    bookings = relationship("Booking", back_populates="business")
    conversations = relationship("Conversation", back_populates="business")
    operating_hours = relationship("BusinessOperatingHours", back_populates="business")
    ai_settings = relationship("BusinessAISettings", back_populates="business", uselist=False)
    notification_settings = relationship("BusinessNotificationSettings", back_populates="business", uselist=False)
    availability_exceptions = relationship("BusinessAvailabilityException", back_populates="business")
    handoff_requests = relationship("HandoffRequest", back_populates="business")