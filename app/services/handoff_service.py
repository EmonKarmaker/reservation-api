import uuid
import secrets
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models import HandoffRequest, Conversation


class HandoffService:
    """
    Service for managing human escalation requests.
    
    Handles:
    - Creating handoff requests when user wants to talk to human
    - Generating ticket IDs for tracking
    - Updating handoff status
    - Retrieving handoff details
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_ticket_id(self) -> str:
        """Generate a unique public ticket ID like HO-ABC123."""
        random_part = secrets.token_hex(3).upper()
        return f"HO-{random_part}"
    
    def _generate_handoff_token(self) -> str:
        """Generate a secure token for status checking."""
        return secrets.token_urlsafe(32)
    
    async def create_handoff(
        self,
        business_id: str,
        conversation_id: str,
        reason: str,
        contact_name: str | None = None,
        contact_phone: str | None = None,
        contact_email: str | None = None,
        booking_id: str | None = None
    ) -> dict:
        """
        Create a new handoff request.
        
        Args:
            business_id: UUID of the business
            conversation_id: UUID of the conversation
            reason: Why the user wants human help
            contact_name: User's name (optional, may already be in booking)
            contact_phone: User's phone
            contact_email: User's email
            booking_id: Associated booking if any
        
        Returns:
            Dictionary with handoff details including ticket ID
        """
        
        # Generate unique ticket ID
        ticket_id = self._generate_ticket_id()
        
        while True:
            existing = await self.db.execute(
                select(HandoffRequest).where(HandoffRequest.public_ticket_id == ticket_id)
            )
            if not existing.scalar_one_or_none():
                break
            ticket_id = self._generate_ticket_id()
        
        # Generate handoff token for secure status checking
        handoff_token = self._generate_handoff_token()
        
        handoff = HandoffRequest(
            business_id=uuid.UUID(business_id),
            conversation_id=uuid.UUID(conversation_id),
            booking_id=uuid.UUID(booking_id) if booking_id else None,
            public_ticket_id=ticket_id,
            handoff_token=handoff_token,
            reason=reason,
            contact_name=contact_name,
            contact_phone=contact_phone,
            contact_email=contact_email,
            status="OPEN",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        
        self.db.add(handoff)
        
        # Update conversation to mark as escalated
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == uuid.UUID(conversation_id))
        )
        conversation = result.scalar_one_or_none()
        
        if conversation:
            conversation.status = "RESOLVED"
            conversation.resolution_type = "HUMAN_ESCALATED"
            conversation.outcome = "ESCALATED"
            conversation.resolved_at = datetime.utcnow()
        
        await self.db.commit()
        await self.db.refresh(handoff)
        
        return {
            "handoff_id": str(handoff.id),
            "public_ticket_id": handoff.public_ticket_id,
            "handoff_token": handoff.handoff_token,
            "status": handoff.status,
            "reason": handoff.reason,
            "created_at": handoff.created_at.isoformat(),
        }
    
    async def get_handoff_by_ticket(self, ticket_id: str) -> dict | None:
        """Get handoff details by public ticket ID."""
        
        result = await self.db.execute(
            select(HandoffRequest).where(HandoffRequest.public_ticket_id == ticket_id)
        )
        handoff = result.scalar_one_or_none()
        
        if not handoff:
            return None
        
        return self._handoff_to_dict(handoff)
    
    async def get_handoff_by_token(self, token: str) -> dict | None:
        """Get handoff details by secure token (for customer status check)."""
        
        result = await self.db.execute(
            select(HandoffRequest).where(HandoffRequest.handoff_token == token)
        )
        handoff = result.scalar_one_or_none()
        
        if not handoff:
            return None
        
        return self._handoff_to_dict(handoff)
    
    async def get_handoff_by_conversation(self, conversation_id: str) -> dict | None:
        """Get the handoff request for a conversation."""
        
        result = await self.db.execute(
            select(HandoffRequest)
            .where(HandoffRequest.conversation_id == uuid.UUID(conversation_id))
            .order_by(HandoffRequest.created_at.desc())
        )
        handoff = result.scalars().first()
        
        if not handoff:
            return None
        
        return self._handoff_to_dict(handoff)
    
    async def update_handoff_status(
        self,
        handoff_id: str,
        status: str,
        admin_notes: str | None = None
    ) -> dict:
        """
        Update handoff status (for admin use).
        
        Args:
            handoff_id: UUID of the handoff
            status: New status (OPEN, ASSIGNED, IN_PROGRESS, RESOLVED, CLOSED)
            admin_notes: Optional notes from admin
        
        Returns:
            Updated handoff details
        """
        
        result = await self.db.execute(
            select(HandoffRequest).where(HandoffRequest.id == uuid.UUID(handoff_id))
        )
        handoff = result.scalar_one_or_none()
        
        if not handoff:
            raise ValueError(f"Handoff not found: {handoff_id}")
        
        handoff.status = status
        handoff.updated_at = datetime.utcnow()
        
        if status in ["RESOLVED", "CLOSED"]:
            handoff.resolved_at = datetime.utcnow()
        
        await self.db.commit()
        
        return self._handoff_to_dict(handoff)
    
    async def get_open_handoffs(self, business_id: str) -> list[dict]:
        """Get all open handoff requests for a business (for admin dashboard)."""
        
        result = await self.db.execute(
            select(HandoffRequest)
            .where(
                HandoffRequest.business_id == uuid.UUID(business_id),
                HandoffRequest.status.in_(["OPEN", "ASSIGNED", "IN_PROGRESS"])
            )
            .order_by(HandoffRequest.created_at.desc())
        )
        handoffs = result.scalars().all()
        
        return [self._handoff_to_dict(h) for h in handoffs]
    
    def _handoff_to_dict(self, handoff: HandoffRequest) -> dict:
        """Convert HandoffRequest model to dictionary."""
        return {
            "handoff_id": str(handoff.id),
            "public_ticket_id": handoff.public_ticket_id,
            "conversation_id": str(handoff.conversation_id) if handoff.conversation_id else None,
            "booking_id": str(handoff.booking_id) if handoff.booking_id else None,
            "status": handoff.status,
            "reason": handoff.reason,
            "contact_name": handoff.contact_name,
            "contact_phone": handoff.contact_phone,
            "contact_email": handoff.contact_email,
            "created_at": handoff.created_at.isoformat() if handoff.created_at else None,
            "resolved_at": handoff.resolved_at.isoformat() if handoff.resolved_at else None,
        }