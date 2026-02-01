import uuid
from datetime import datetime, date, time, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.models import (
    Booking,
    Service,
    BusinessOperatingHours,
    BusinessAvailabilityException,
    ServiceCapacityRule,
)


class SlotService:
    """
    Service for managing time slot availability.
    
    Handles:
    - Generating available slots for a service on a date
    - Checking if a specific slot is available
    - Respecting business hours and exceptions
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_available_slots(
        self,
        business_id: str,
        service_id: str,
        target_date: date,
        slot_duration_minutes: int = 60
    ) -> list[dict]:
        """
        Get all available time slots for a service on a specific date.
        
        Args:
            business_id: UUID of the business
            service_id: UUID of the service
            target_date: The date to check availability
            slot_duration_minutes: Duration of each slot (default 60 min)
        
        Returns:
            List of available slots with start and end times
        """
        
        # Step 1: Get business operating hours for this day
        day_of_week = target_date.weekday()  # 0=Monday, 6=Sunday
        
        result = await self.db.execute(
            select(BusinessOperatingHours).where(
                BusinessOperatingHours.business_id == uuid.UUID(business_id),
                BusinessOperatingHours.day_of_week == day_of_week
            )
        )
        operating_hours = result.scalar_one_or_none()
        
        # If no hours defined or closed, return empty
        if not operating_hours or operating_hours.is_closed:
            return []
        
        if not operating_hours.open_time or not operating_hours.close_time:
            return []
        
        # Step 2: Check for exceptions (holidays, special closures)
        target_datetime_start = datetime.combine(target_date, time.min)
        target_datetime_end = datetime.combine(target_date, time.max)
        
        result = await self.db.execute(
            select(BusinessAvailabilityException).where(
                BusinessAvailabilityException.business_id == uuid.UUID(business_id),
                BusinessAvailabilityException.start_at <= target_datetime_end,
                BusinessAvailabilityException.end_at >= target_datetime_start,
                BusinessAvailabilityException.exception_type == 'CLOSED'
            )
        )
        closure = result.scalar_one_or_none()
        
        if closure:
            return []  # Business is closed on this date
        
        # Step 3: Generate all possible slots
        open_time = operating_hours.open_time
        close_time = operating_hours.close_time
        
        slots = []
        current_time = datetime.combine(target_date, open_time)
        end_of_day = datetime.combine(target_date, close_time)
        
        while current_time + timedelta(minutes=slot_duration_minutes) <= end_of_day:
            slot_end = current_time + timedelta(minutes=slot_duration_minutes)
            slots.append({
                "start": current_time,
                "end": slot_end
            })
            current_time = slot_end
        
        # Step 4: Filter out already booked slots
        available_slots = []
        
        for slot in slots:
            is_available = await self.check_slot_available(
                service_id=service_id,
                slot_start=slot["start"],
                slot_end=slot["end"]
            )
            
            if is_available:
                available_slots.append({
                    "start": slot["start"].isoformat(),
                    "end": slot["end"].isoformat(),
                    "available": True
                })
        
        return available_slots
    
    async def check_slot_available(
        self,
        service_id: str,
        slot_start: datetime,
        slot_end: datetime | None = None
    ) -> bool:
        """
        Check if a specific time slot is available for booking.
        
        Args:
            service_id: UUID of the service
            slot_start: Start datetime of the slot
            slot_end: End datetime (optional, not used in simple check)
        
        Returns:
            True if slot is available, False if already booked
        """
        
        # Find any existing booking for this service at this time
        # Exclude cancelled, failed, and expired bookings
        result = await self.db.execute(
            select(Booking).where(
                Booking.service_id == uuid.UUID(service_id),
                Booking.slot_start == slot_start,
                Booking.status.notin_(['CANCELLED', 'CANCELED', 'FAILED', 'EXPIRED'])
            )
        )
        existing_booking = result.scalar_one_or_none()
        
        # Slot is available if no existing booking found
        return existing_booking is None
    
    async def get_alternative_slots(
        self,
        business_id: str,
        service_id: str,
        requested_slot: datetime,
        num_alternatives: int = 5
    ) -> list[dict]:
        """
        Get alternative available slots near the requested time.
        
        Used when user's preferred slot is not available.
        
        Args:
            business_id: UUID of the business
            service_id: UUID of the service
            requested_slot: The slot user wanted but isn't available
            num_alternatives: How many alternatives to return
        
        Returns:
            List of alternative available slots
        """
        
        # Get slots for the same day
        target_date = requested_slot.date()
        all_slots = await self.get_available_slots(
            business_id=business_id,
            service_id=service_id,
            target_date=target_date
        )
        
        # If not enough slots today, also check tomorrow
        if len(all_slots) < num_alternatives:
            tomorrow = target_date + timedelta(days=1)
            tomorrow_slots = await self.get_available_slots(
                business_id=business_id,
                service_id=service_id,
                target_date=tomorrow
            )
            all_slots.extend(tomorrow_slots)
        
        # Sort by closeness to requested time
        def time_distance(slot):
            slot_start = datetime.fromisoformat(slot["start"])
            return abs((slot_start - requested_slot).total_seconds())
        
        all_slots.sort(key=time_distance)
        
        return all_slots[:num_alternatives]
    
    async def validate_and_reserve_slot(
        self,
        service_id: str,
        slot_start: datetime,
        slot_end: datetime
    ) -> dict:
        """
        Validate slot availability and return result.
        
        This is the main method to call before confirming a slot selection.
        
        Args:
            service_id: UUID of the service
            slot_start: Requested slot start time
            slot_end: Requested slot end time
        
        Returns:
            {
                "available": True/False,
                "message": "Success" or "Slot not available",
                "alternatives": [...] if not available
            }
        """
        
        is_available = await self.check_slot_available(
            service_id=service_id,
            slot_start=slot_start,
            slot_end=slot_end
        )
        
        if is_available:
            return {
                "available": True,
                "message": "Slot is available"
            }
        else:
            # Get the service to find business_id
            result = await self.db.execute(
                select(Service).where(Service.id == uuid.UUID(service_id))
            )
            service = result.scalar_one_or_none()
            
            alternatives = []
            if service:
                alternatives = await self.get_alternative_slots(
                    business_id=str(service.business_id),
                    service_id=service_id,
                    requested_slot=slot_start
                )
            
            return {
                "available": False,
                "message": "This slot is no longer available. Please choose another time.",
                "alternatives": alternatives
            }