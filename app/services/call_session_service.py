import uuid
import secrets
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.models import CallSession, Conversation


class CallSessionService:
    """
    Service for managing voice call sessions.
    
    Handles:
    - Creating call sessions with unique IDs
    - Updating call status and transcript
    - Searching calls by various criteria
    - Analytics and reporting
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    def _generate_call_id(self) -> str:
        """Generate a unique public call ID like CALL-ABC123."""
        random_part = secrets.token_hex(3).upper()
        return f"CALL-{random_part}"
    
    async def start_call(
        self,
        business_id: str,
        caller_phone: str | None = None,
        provider_call_id: str | None = None,
        channel: str = "VOICE"
    ) -> dict:
        """
        Start a new call session.
        
        Args:
            business_id: UUID of the business
            caller_phone: Caller's phone number
            provider_call_id: External provider's call ID (Vapi, Twilio)
            channel: VOICE or WHATSAPP_VOICE
        
        Returns:
            Call session details including public_call_id
        """
        
        # Generate unique call ID
        call_id = self._generate_call_id()
        
        while True:
            existing = await self.db.execute(
                select(CallSession).where(CallSession.public_call_id == call_id)
            )
            if not existing.scalar_one_or_none():
                break
            call_id = self._generate_call_id()
        
        # Create associated conversation for message storage
        conversation = Conversation(
            business_id=uuid.UUID(business_id),
            channel="VOICE",
            status="STARTED",
            started_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        await self.db.flush()
        
        # Create call session
        call_session = CallSession(
            business_id=uuid.UUID(business_id),
            public_call_id=call_id,
            provider_call_id=provider_call_id,
            caller_phone=caller_phone,
            channel=channel,
            status="IN_PROGRESS",
            conversation_id=conversation.id,
            started_at=datetime.utcnow(),
            answered_at=datetime.utcnow(),
        )
        
        self.db.add(call_session)
        await self.db.commit()
        await self.db.refresh(call_session)
        
        return {
            "call_session_id": str(call_session.id),
            "public_call_id": call_session.public_call_id,
            "conversation_id": str(call_session.conversation_id),
            "status": call_session.status,
            "started_at": call_session.started_at.isoformat(),
        }
    
    async def update_transcript(
        self,
        call_session_id: str,
        transcript: str,
        ai_messages: int = 0,
        user_messages: int = 0
    ) -> dict:
        """Update the call transcript."""
        
        result = await self.db.execute(
            select(CallSession).where(CallSession.id == uuid.UUID(call_session_id))
        )
        call_session = result.scalar_one_or_none()
        
        if not call_session:
            raise ValueError(f"Call session not found: {call_session_id}")
        
        call_session.full_transcript = transcript
        call_session.total_ai_messages = ai_messages
        call_session.total_user_messages = user_messages
        call_session.updated_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {"status": "updated"}
    
    async def end_call(
        self,
        call_session_id: str,
        status: str = "COMPLETED",
        resolution_type: str | None = None,
        outcome: str | None = None,
        booking_id: str | None = None,
        handoff_id: str | None = None
    ) -> dict:
        """End a call session."""
        
        result = await self.db.execute(
            select(CallSession).where(CallSession.id == uuid.UUID(call_session_id))
        )
        call_session = result.scalar_one_or_none()
        
        if not call_session:
            raise ValueError(f"Call session not found: {call_session_id}")
        
        call_session.status = status
        call_session.resolution_type = resolution_type
        call_session.outcome = outcome
        call_session.ended_at = datetime.utcnow()
        
        # Calculate duration
        if call_session.started_at:
            duration = (datetime.utcnow() - call_session.started_at.replace(tzinfo=None)).total_seconds()
            call_session.duration_seconds = int(duration)
        
        if booking_id:
            call_session.booking_id = uuid.UUID(booking_id)
        
        if handoff_id:
            call_session.handoff_id = uuid.UUID(handoff_id)
        
        # Update associated conversation
        if call_session.conversation_id:
            conv_result = await self.db.execute(
                select(Conversation).where(Conversation.id == call_session.conversation_id)
            )
            conversation = conv_result.scalar_one_or_none()
            if conversation:
                conversation.status = "RESOLVED"
                conversation.resolution_type = resolution_type
                conversation.resolved_at = datetime.utcnow()
        
        await self.db.commit()
        
        return {
            "call_session_id": str(call_session.id),
            "public_call_id": call_session.public_call_id,
            "status": call_session.status,
            "duration_seconds": call_session.duration_seconds,
            "resolution_type": call_session.resolution_type,
            "outcome": call_session.outcome,
        }
    
    async def get_call_by_public_id(self, public_call_id: str) -> dict | None:
        """Get call session by public ID (CALL-XXXXXX)."""
        
        result = await self.db.execute(
            select(CallSession).where(CallSession.public_call_id == public_call_id)
        )
        call_session = result.scalar_one_or_none()
        
        if not call_session:
            return None
        
        return self._call_to_dict(call_session)
    
    async def get_call_by_provider_id(self, provider_call_id: str) -> dict | None:
        """Get call session by provider's call ID (Vapi, Twilio SID)."""
        
        result = await self.db.execute(
            select(CallSession).where(CallSession.provider_call_id == provider_call_id)
        )
        call_session = result.scalar_one_or_none()
        
        if not call_session:
            return None
        
        return self._call_to_dict(call_session)
    
    async def search_calls(
        self,
        business_id: str,
        phone: str | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        keyword: str | None = None,
        limit: int = 50,
        offset: int = 0
    ) -> dict:
        """Search call sessions with various filters."""
        
        query = select(CallSession).where(
            CallSession.business_id == uuid.UUID(business_id)
        )
        
        if phone:
            query = query.where(CallSession.caller_phone.ilike(f"%{phone}%"))
        
        if status:
            query = query.where(CallSession.status == status)
        
        if date_from:
            query = query.where(CallSession.started_at >= date_from)
        
        if date_to:
            query = query.where(CallSession.started_at <= date_to)
        
        if keyword:
            query = query.where(
                CallSession.transcript_search.match(keyword)
            )
        
        # Get total count
        count_query = select(func.count()).select_from(query.subquery())
        count_result = await self.db.execute(count_query)
        total_count = count_result.scalar()
        
        # Get results with pagination
        query = query.order_by(CallSession.started_at.desc()).limit(limit).offset(offset)
        result = await self.db.execute(query)
        calls = result.scalars().all()
        
        return {
            "total": total_count,
            "limit": limit,
            "offset": offset,
            "calls": [self._call_to_dict(c) for c in calls]
        }
    
    async def get_call_analytics(
        self,
        business_id: str,
        date_from: datetime | None = None,
        date_to: datetime | None = None
    ) -> dict:
        """Get call analytics for a business."""
        
        base_query = select(CallSession).where(
            CallSession.business_id == uuid.UUID(business_id)
        )
        
        if date_from:
            base_query = base_query.where(CallSession.started_at >= date_from)
        if date_to:
            base_query = base_query.where(CallSession.started_at <= date_to)
        
        result = await self.db.execute(base_query)
        calls = result.scalars().all()
        
        total_calls = len(calls)
        completed_calls = sum(1 for c in calls if c.status == "COMPLETED")
        escalated_calls = sum(1 for c in calls if c.status == "ESCALATED")
        abandoned_calls = sum(1 for c in calls if c.status == "ABANDONED")
        
        ai_resolved = sum(1 for c in calls if c.resolution_type == "AI_RESOLVED")
        human_escalated = sum(1 for c in calls if c.resolution_type == "HUMAN_ESCALATED")
        
        durations = [c.duration_seconds for c in calls if c.duration_seconds]
        avg_duration = sum(durations) / len(durations) if durations else 0
        
        ai_resolution_rate = (ai_resolved / total_calls * 100) if total_calls > 0 else 0
        
        return {
            "total_calls": total_calls,
            "by_status": {
                "completed": completed_calls,
                "escalated": escalated_calls,
                "abandoned": abandoned_calls,
                "in_progress": sum(1 for c in calls if c.status == "IN_PROGRESS"),
                "failed": sum(1 for c in calls if c.status == "FAILED"),
            },
            "by_resolution": {
                "ai_resolved": ai_resolved,
                "human_escalated": human_escalated,
                "user_abandoned": sum(1 for c in calls if c.resolution_type == "USER_ABANDONED"),
            },
            "avg_duration_seconds": round(avg_duration, 2),
            "ai_resolution_rate_percent": round(ai_resolution_rate, 2),
        }
    
    def _call_to_dict(self, call: CallSession) -> dict:
        """Convert CallSession model to dictionary."""
        return {
            "call_session_id": str(call.id),
            "public_call_id": call.public_call_id,
            "provider_call_id": call.provider_call_id,
            "caller_phone": call.caller_phone,
            "channel": call.channel,
            "status": call.status,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "duration_seconds": call.duration_seconds,
            "total_ai_messages": call.total_ai_messages,
            "total_user_messages": call.total_user_messages,
            "resolution_type": call.resolution_type,
            "outcome": call.outcome,
            "conversation_id": str(call.conversation_id) if call.conversation_id else None,
            "booking_id": str(call.booking_id) if call.booking_id else None,
            "handoff_id": str(call.handoff_id) if call.handoff_id else None,
            "full_transcript": call.full_transcript,
        }