from pydantic import BaseModel, Field
from datetime import datetime
from decimal import Decimal
from uuid import UUID


# ============== Service Image Schemas ==============

class ServiceImageResponse(BaseModel):
    id: UUID
    image_url: str
    alt_text: str | None = None
    sort_order: int

    class Config:
        from_attributes = True


# ============== Service Capacity Schemas ==============

class ServiceCapacityResponse(BaseModel):
    capacity: int
    slot_length_minutes: int

    class Config:
        from_attributes = True


# ============== Service Schemas ==============

class ServiceBase(BaseModel):
    service_name: str = Field(..., min_length=1, max_length=200)
    description: str | None = None
    base_price: Decimal | None = Field(None, ge=0)
    currency: str | None = Field(None, min_length=3, max_length=3)
    duration_minutes: int | None = Field(None, gt=0)
    is_active: bool = True


class ServiceCreate(ServiceBase):
    slug: str = Field(..., min_length=1, max_length=140)


class ServiceUpdate(BaseModel):
    service_name: str | None = Field(None, min_length=1, max_length=200)
    description: str | None = None
    base_price: Decimal | None = None
    currency: str | None = None
    duration_minutes: int | None = None
    is_active: bool | None = None


class ServiceResponse(ServiceBase):
    """Basic service info returned in lists."""
    id: UUID
    business_id: UUID
    slug: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ServiceDetailResponse(ServiceResponse):
    """Full service details with images and capacity - used when user asks for details."""
    images: list[ServiceImageResponse] = []
    capacity_rule: ServiceCapacityResponse | None = None


# ============== Service List for Chatbot ==============

class ServiceListItem(BaseModel):
    """Minimal service info for chatbot to show options."""
    id: UUID
    slug: str
    service_name: str
    base_price: Decimal | None = None
    currency: str | None = None
    duration_minutes: int | None = None

    class Config:
        from_attributes = True