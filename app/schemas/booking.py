from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from uuid import UUID


# ============== Time Slot Schemas ==============

class TimeSlot(BaseModel):
    """A single available time slot."""
    start: datetime
    end: datetime
    available: bool = True


class AvailableSlotsResponse(BaseModel):
    """List of available slots for a service on a given date."""
    service_id: UUID
    date: str
    slots: list[TimeSlot]


# ============== Contact Info Schema ==============

class CustomerContact(BaseModel):
    """Contact info collected from customer."""
    customer_name: str = Field(..., min_length=1, max_length=120)
    customer_phone: str = Field(..., min_length=6, max_length=40)
    customer_email: EmailStr


# ============== Booking Schemas ==============

class BookingCreate(BaseModel):
    """Initial booking creation - just service selection."""
    service_id: UUID


class BookingSlotSelect(BaseModel):
    """Select a time slot for the booking."""
    slot_start: datetime
    slot_end: datetime


class BookingContactUpdate(CustomerContact):
    """Update booking with customer contact info."""
    pass


class BookingResponse(BaseModel):
    """Booking info returned to customer."""
    id: UUID
    public_tracking_id: str
    service_id: UUID
    status: str
    slot_start: datetime | None = None
    slot_end: datetime | None = None
    customer_name: str | None = None
    customer_email: str | None = None
    payment_status: str
    created_at: datetime

    class Config:
        from_attributes = True


class BookingDetailResponse(BookingResponse):
    """Full booking details for admin or customer lookup."""
    business_id: UUID
    conversation_id: UUID | None = None
    resolution_type: str | None = None
    customer_phone: str | None = None
    notes: str | None = None
    paid_at: datetime | None = None
    confirmed_at: datetime | None = None
    updated_at: datetime


class BookingStatusUpdate(BaseModel):
    """Admin updating booking status."""
    status: str
    change_reason: str | None = None


# ============== Booking Lookup ==============

class BookingLookupRequest(BaseModel):
    """Customer looking up their booking by tracking ID."""
    tracking_id: str = Field(..., min_length=1, max_length=20)


class BookingPublicResponse(BaseModel):
    """Limited booking info shown to customer via tracking ID."""
    public_tracking_id: str
    status: str
    service_name: str
    slot_start: datetime | None = None
    slot_end: datetime | None = None
    payment_status: str

# ============== Error Responses ==============

class SlotUnavailableError(BaseModel):
    """Returned when requested slot is no longer available."""
    error: str = "slot_unavailable"
    message: str = "The requested time slot is no longer available."
    available_slots: list[TimeSlot] = []