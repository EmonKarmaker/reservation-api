from sqlalchemy import String, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import DateTime

from app.core.database import Base


class BusinessProfile(Base):
    __tablename__ = "business_profiles"
    __table_args__ = {"schema": "core"}

    business_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.businesses.id", ondelete="CASCADE"),
        primary_key=True,
    )

    contact_person: Mapped[str | None] = mapped_column(String(120), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
