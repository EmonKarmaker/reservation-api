import uuid
import secrets
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import Booking, Service


class BookingService:
    """
    Service for creating and managing bookings.
    Persists booking state between conversation messages.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_tracking_id(self) -> str:
        """Generate a unique public tracking ID like BK-A1B2C3."""
        random_part = secrets.token_hex(3).upper()
        return f"BK-{random_part}"
    
    async def create_booking(
        self,
        business_id: str,
        service_id: str,
        conversation_id: str | None = None
    ) -> dict:
        """
        Create a new booking in INITIATED status.
        Called when user selects a service.
        """
        
        tracking_id = self._generate_tracking_id()
        
        # Ensure tracking ID is unique
        while True:
            existing = await self.db.execute(
                select(Booking).where(Booking.public_tracking_id == tracking_id)
            )
            if not existing.scalar_one_or_none():
                break
            tracking_id = self._generate_tracking_id()
        
        booking = Booking(
            business_id=uuid.UUID(business_id),
            service_id=uuid.UUID(service_id),
            conversation_id=uuid.UUID(conversation_id) if conversation_id else None,
            public_tracking_id=tracking_id,
            status="INITIATED",
            payment_status="CREATED",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(booking)
        await self.db.commit()
        await self.db.refresh(booking)
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "status": booking.status,
        }
    
    async def update_slot(
        self,
        booking_id: str,
        slot_start: datetime,
        slot_end: datetime
    ) -> dict:
        """Update booking with selected time slot."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {booking_id}")
        
        booking.slot_start = slot_start
        booking.slot_end = slot_end
        booking.status = "SLOT_SELECTED"
        booking.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "booking_id": str(booking.id),
            "status": booking.status,
            "slot_start": booking.slot_start.isoformat() if booking.slot_start else None,
            "slot_end": booking.slot_end.isoformat() if booking.slot_end else None,
        }
    
    async def update_contact(
        self,
        booking_id: str,
        customer_name: str,
        customer_phone: str,
        customer_email: str
    ) -> dict:
        """Update booking with customer contact information."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {booking_id}")
        
        booking.customer_name = customer_name
        booking.customer_phone = customer_phone
        booking.customer_email = customer_email
        booking.contact_collected_at = datetime.utcnow()
        booking.status = "CONTACT_COLLECTED"
        booking.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "status": booking.status,
        }
    
    async def confirm_booking(self, booking_id: str) -> dict:
        """Confirm a booking."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {booking_id}")
        
        booking.status = "CONFIRMED"
        booking.confirmed_at = datetime.utcnow()
        booking.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "status": booking.status,
            "confirmed_at": booking.confirmed_at.isoformat(),
        }
    
    async def get_booking(self, booking_id: str) -> dict | None:
        """Get booking details by ID."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            return None
        
        # Get service name
        service_result = await self.db.execute(
            select(Service).where(Service.id == booking.service_id)
        )
        service = service_result.scalar_one_or_none()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "service_id": str(booking.service_id),
            "service_name": service.service_name if service else None,
            "status": booking.status,
            "slot_start": booking.slot_start.isoformat() if booking.slot_start else None,
            "slot_end": booking.slot_end.isoformat() if booking.slot_end else None,
            "customer_name": booking.customer_name,
            "customer_phone": booking.customer_phone,
            "customer_email": booking.customer_email,
            "payment_status": booking.payment_status,
        }
    
    async def get_booking_by_conversation(self, conversation_id: str) -> dict | None:
        """Get the active booking for a conversation."""
        
        result = await self.db.execute(
            select(Booking)
            .where(Booking.conversation_id == uuid.UUID(conversation_id))
            .where(Booking.status.notin_(["CANCELLED", "CANCELED", "FAILED", "EXPIRED"]))
            .order_by(Booking.created_at.desc())
        )
        booking = result.scalars().first()
        
        if not booking:
            return None
        
        return await self.get_booking(str(booking.id))
    
    async def check_slot_available(
        self,
        service_id: str,
        slot_start: datetime
    ) -> bool:
        """Check if a time slot is available."""
        
        result = await self.db.execute(
            select(Booking).where(
                Booking.service_id == uuid.UUID(service_id),
                Booking.slot_start == slot_start,
                Booking.status.notin_(["CANCELLED", "CANCELED", "FAILED", "EXPIRED"])
            )
        )
        existing = result.scalar_one_or_none()
        
        return existing is None
    
    async def get_booking_by_tracking_id(self, tracking_id: str) -> dict | None:
        """Get booking details by public tracking ID (like BK-XXXXXX)."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.public_tracking_id == tracking_id)
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            return None
        
        # Get service name
        service_result = await self.db.execute(
            select(Service).where(Service.id == booking.service_id)
        )
        service = service_result.scalar_one_or_none()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "service_id": str(booking.service_id),
            "service_name": service.service_name if service else None,
            "status": booking.status,
            "slot_start": booking.slot_start.isoformat() if booking.slot_start else None,
            "slot_end": booking.slot_end.isoformat() if booking.slot_end else None,
            "customer_name": booking.customer_name,
            "customer_phone": booking.customer_phone,
            "customer_email": booking.customer_email,
            "payment_status": booking.payment_status,
            "confirmed_at": booking.confirmed_at.isoformat() if booking.confirmed_at else None,
        }
    
    async def cancel_booking(self, booking_id: str, reason: str = "User requested cancellation") -> dict:
        """Cancel a booking."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {booking_id}")
        
        if booking.status in ["CANCELLED", "CANCELED"]:
            raise ValueError("Booking is already cancelled")
        
        booking.status = "CANCELLED"
        booking.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "status": booking.status,
            "message": "Booking has been cancelled successfully"
        }
    
    async def cancel_booking_by_tracking_id(self, tracking_id: str) -> dict:
        """Cancel a booking by its public tracking ID."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.public_tracking_id == tracking_id)
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {tracking_id}")
        
        if booking.status in ["CANCELLED", "CANCELED"]:
            raise ValueError("Booking is already cancelled")
        
        booking.status = "CANCELLED"
        booking.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "status": booking.status,
            "message": "Booking has been cancelled successfully"
        }
    
    async def reschedule_booking(
        self,
        booking_id: str,
        new_slot_start: datetime,
        new_slot_end: datetime
    ) -> dict:
        """Reschedule a booking to a new time slot."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.id == uuid.UUID(booking_id))
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {booking_id}")
        
        if booking.status in ["CANCELLED", "CANCELED", "FAILED"]:
            raise ValueError("Cannot reschedule a cancelled or failed booking")
        
        # Update slot times
        booking.slot_start = new_slot_start
        booking.slot_end = new_slot_end
        booking.status = "RESCHEDULED"
        booking.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "booking_id": str(booking.id),
            "public_tracking_id": booking.public_tracking_id,
            "status": booking.status,
            "new_slot_start": new_slot_start.isoformat(),
            "new_slot_end": new_slot_end.isoformat(),
            "message": "Booking has been rescheduled successfully"
        }
    
    async def reschedule_booking_by_tracking_id(
        self,
        tracking_id: str,
        new_slot_start: datetime,
        new_slot_end: datetime
    ) -> dict:
        """Reschedule a booking by its tracking ID."""
        
        result = await self.db.execute(
            select(Booking).where(Booking.public_tracking_id == tracking_id)
        )
        booking = result.scalar_one_or_none()
        
        if not booking:
            raise ValueError(f"Booking not found: {tracking_id}")
        
        return await self.reschedule_booking(
            booking_id=str(booking.id),
            new_slot_start=new_slot_start,
            new_slot_end=new_slot_end
        )