from __future__ import annotations

from datetime import time
from typing import Optional, Literal, List

from pydantic import BaseModel, EmailStr, Field


ALLOWED_INDUSTRIES = {"HOTEL", "RESTAURANT", "SALON", "CLINIC", "OTHER", "SPA"}


class OperatingHoursRule(BaseModel):
    """
    IMPORTANT: matches your model comment:
      0 = Monday, 6 = Sunday
    """
    day_of_week: int = Field(ge=0, le=6)
    open_time: Optional[time] = None
    close_time: Optional[time] = None
    is_closed: bool = False


class OperatingHoursBulk(BaseModel):
    timezone: Optional[str] = None
    weekly_hours: List[OperatingHoursRule]


class BusinessProfileIn(BaseModel):
    contact_person: Optional[str] = Field(default=None, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)


class BusinessAddressIn(BaseModel):
    address_type: Literal["PRIMARY", "BILLING", "BRANCH"] = "PRIMARY"
    street: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    zip_code: Optional[str] = Field(default=None, max_length=30)
    country: Optional[str] = Field(default=None, max_length=100)


class BusinessCreate(BaseModel):
    # Core identity
    business_name: str
    slug: str
    industry: str = "HOTEL"
    timezone: str = "Asia/Dhaka"

    # OPTIONAL onboarding (enterprise)
    profile: Optional[BusinessProfileIn] = None
    address: Optional[BusinessAddressIn] = None
    hours: Optional[OperatingHoursBulk] = None


class BusinessUpdate(BaseModel):
    business_name: str | None = None
    timezone: str | None = None
    status: str | None = None


class BusinessResponse(BaseModel):
    id: str
    business_name: str
    slug: str
    industry: str
    industry_label: str | None = None
    timezone: str
    status: str | None
    created_at: str | None


class BusinessProfileResponse(BaseModel):
    business_id: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None


class BusinessAddressResponse(BaseModel):
    id: str
    business_id: str
    address_type: str
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None


class OperatingHoursResponse(BaseModel):
    business_id: str
    weekly_hours: list[OperatingHoursRule]


class AISettingsUpdate(BaseModel):
    agent_name: str | None = None
    tone_of_voice: str | None = None
    welcome_message: str | None = None
    fallback_message: str | None = None
    escalation_message: str | None = None
    max_retries: int | None = None
    language: str | None = None


class AISettingsResponse(BaseModel):
    id: str
    business_id: str
    agent_name: str
    tone_of_voice: str | None
    welcome_message: str | None
    fallback_message: str | None
    escalation_message: str | None
    max_retries: int | None
    language: str | None
