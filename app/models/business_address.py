from sqlalchemy import String, ForeignKey, func, Enum, UniqueConstraint, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql.sqltypes import DateTime

from app.core.database import Base


class BusinessAddress(Base):
    __tablename__ = "business_addresses"
    __table_args__ = (
        UniqueConstraint("business_id", "address_type", name="uq_business_address_type"),
        {"schema": "core"},
    )

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    business_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("core.businesses.id", ondelete="CASCADE"),
        nullable=False,
    )

    # matches core.address_type_enum
    address_type: Mapped[str] = mapped_column(
        Enum("PRIMARY", "BILLING", "BRANCH", name="address_type_enum", schema="core"),
        nullable=False,
        default="PRIMARY",
    )

    street: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    zip_code: Mapped[str | None] = mapped_column(String(30), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
