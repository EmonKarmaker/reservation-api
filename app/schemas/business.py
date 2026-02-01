from pydantic import BaseModel, Field
from datetime import datetime, time
from decimal import Decimal
from uuid import UUID


# ============== Business Schemas ==============

class BusinessBase(BaseModel):
    """Fields common to create and update operations."""
    business_name: str = Field(..., min_length=1, max_length=200)
    industry: str = Field(..., min_length=1, max_length=50)
    timezone: str = Field(..., min_length=1, max_length=64)


class BusinessCreate(BusinessBase):
    """Fields required when creating a new business."""
    slug: str = Field(..., min_length=1, max_length=120)


class BusinessUpdate(BaseModel):
    """Fields that can be updated. All optional."""
    business_name: str | None = Field(None, min_length=1, max_length=200)
    industry: str | None = None
    timezone: str | None = None
    status: str | None = None


class BusinessResponse(BusinessBase):
    """Fields returned when reading a business."""
    id: UUID
    slug: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============== Operating Hours Schemas ==============

class OperatingHoursBase(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    open_time: time | None = None
    close_time: time | None = None
    is_closed: bool = False


class OperatingHoursCreate(OperatingHoursBase):
    pass


class OperatingHoursResponse(OperatingHoursBase):
    id: UUID

    class Config:
        from_attributes = True


# ============== AI Settings Schemas ==============

class AISettingsBase(BaseModel):
    agent_name: str = Field(..., min_length=1, max_length=120)
    tone_of_voice: str | None = Field(None, max_length=120)
    personality: str | None = None
    business_display_name: str | None = Field(None, max_length=200)
    is_ai_enabled: bool = True
    fallback_to_human: bool = True
    voice_id: str | None = Field(None, max_length=120)
    confidence_threshold: Decimal = Field(default=Decimal("0.650"), ge=0, le=1)
    allow_cancel_bookings: bool = False
    allow_reschedule_bookings: bool = False
    mention_promotions: bool = False


class AISettingsCreate(AISettingsBase):
    pass


class AISettingsUpdate(BaseModel):
    agent_name: str | None = Field(None, min_length=1, max_length=120)
    tone_of_voice: str | None = None
    personality: str | None = None
    business_display_name: str | None = None
    is_ai_enabled: bool | None = None
    fallback_to_human: bool | None = None
    voice_id: str | None = None
    confidence_threshold: Decimal | None = Field(None, ge=0, le=1)
    allow_cancel_bookings: bool | None = None
    allow_reschedule_bookings: bool | None = None
    mention_promotions: bool | None = None


class AISettingsResponse(AISettingsBase):
    id: UUID
    business_id: UUID

    class Config:
        from_attributes = True


# ============== Notification Settings Schemas ==============

class NotificationSettingsBase(BaseModel):
    email_alerts_enabled: bool = False
    sms_alerts_enabled: bool = False
    whatsapp_alerts_enabled: bool = False


class NotificationSettingsUpdate(NotificationSettingsBase):
    pass


class NotificationSettingsResponse(NotificationSettingsBase):
    id: UUID
    business_id: UUID

    class Config:
        from_attributes = True


# ============== Full Business Response (with related data) ==============

class BusinessFullResponse(BusinessResponse):
    """Business with all related settings included."""
    ai_settings: AISettingsResponse | None = None
    notification_settings: NotificationSettingsResponse | None = None
    operating_hours: list[OperatingHoursResponse] = []