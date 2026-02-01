from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime
import uuid as uuid_lib

from app.core.database import get_db
from app.services.call_session_service import CallSessionService
from app.services.voice_chat_service import VoiceChatService
from app.models import CallSession


router = APIRouter()


# ============== Request/Response Models ==============

class StartCallRequest(BaseModel):
    business_id: str
    caller_phone: str | None = None
    provider_call_id: str | None = None
    channel: str = "VOICE"


class VoiceMessageRequest(BaseModel):
    call_session_id: str
    message: str


class EndCallRequest(BaseModel):
    call_session_id: str
    status: str = "COMPLETED"
    resolution_type: str | None = None
    outcome: str | None = None


class SearchCallsRequest(BaseModel):
    business_id: str
    phone: str | None = None
    status: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    keyword: str | None = None
    limit: int = 50
    offset: int = 0


# ============== Endpoints ==============

@router.post("/calls/start")
async def start_call(
    request: StartCallRequest,
    db: AsyncSession = Depends(get_db)
):
    """Start a new voice call session."""
    try:
        call_service = CallSessionService(db)
        
        result = await call_service.start_call(
            business_id=request.business_id,
            caller_phone=request.caller_phone,
            provider_call_id=request.provider_call_id,
            channel=request.channel
        )
        
        result["greeting"] = f"Welcome! Your call reference is {result['public_call_id'][-6:]}. How can I help you today?"
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calls/message")
async def process_voice_message(
    request: VoiceMessageRequest,
    db: AsyncSession = Depends(get_db)
):
    """Process a voice message from customer."""
    try:
        call_service = CallSessionService(db)
        chat_service = VoiceChatService(db)
        
        from sqlalchemy import select
        
        # Find call session by ID or public_call_id
        try:
            call_uuid = uuid_lib.UUID(request.call_session_id)
            result = await db.execute(
                select(CallSession).where(CallSession.id == call_uuid)
            )
        except ValueError:
            result = await db.execute(
                select(CallSession).where(CallSession.public_call_id == request.call_session_id)
            )
        
        call_session = result.scalar_one_or_none()
        
        if not call_session:
            raise HTTPException(status_code=404, detail="Call session not found")
        
        # Process message through chat service
        chat_result = await chat_service.send_message(
            conversation_id=str(call_session.conversation_id),
            user_message=request.message
        )
        
        needs_human = chat_result.get("needs_escalation", False)
        response_text = chat_result.get("response", "I'm sorry, I didn't understand that.")
        
        if needs_human:
            response_text = "I'll connect you with a representative. Please press 0 to speak with a human agent."
        
        return {
            "response": response_text,
            "intent": chat_result.get("intent"),
            "needs_human": needs_human,
            "booking_id": chat_result.get("public_tracking_id"),
            "booking_status": chat_result.get("booking_status"),
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calls/end")
async def end_call(
    request: EndCallRequest,
    db: AsyncSession = Depends(get_db)
):
    """End a voice call session."""
    try:
        call_service = CallSessionService(db)
        
        from sqlalchemy import select
        
        try:
            call_uuid = uuid_lib.UUID(request.call_session_id)
            result = await db.execute(
                select(CallSession).where(CallSession.id == call_uuid)
            )
        except ValueError:
            result = await db.execute(
                select(CallSession).where(CallSession.public_call_id == request.call_session_id)
            )
        
        call_session = result.scalar_one_or_none()
        
        if not call_session:
            raise HTTPException(status_code=404, detail="Call session not found")
        
        end_result = await call_service.end_call(
            call_session_id=str(call_session.id),
            status=request.status,
            resolution_type=request.resolution_type,
            outcome=request.outcome
        )
        
        return end_result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/{call_id}")
async def get_call(
    call_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get call session details."""
    try:
        call_service = CallSessionService(db)
        
        call = await call_service.get_call_by_public_id(call_id)
        
        if not call:
            from sqlalchemy import select
            try:
                result = await db.execute(
                    select(CallSession).where(CallSession.id == uuid_lib.UUID(call_id))
                )
                call_session = result.scalar_one_or_none()
                if call_session:
                    call = call_service._call_to_dict(call_session)
            except:
                pass
        
        if not call:
            raise HTTPException(status_code=404, detail="Call not found")
        
        return call
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/calls/search")
async def search_calls(
    request: SearchCallsRequest,
    db: AsyncSession = Depends(get_db)
):
    """Search call sessions with filters."""
    try:
        call_service = CallSessionService(db)
        
        results = await call_service.search_calls(
            business_id=request.business_id,
            phone=request.phone,
            status=request.status,
            date_from=request.date_from,
            date_to=request.date_to,
            keyword=request.keyword,
            limit=request.limit,
            offset=request.offset
        )
        
        return results
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calls/analytics/{business_id}")
async def get_call_analytics(
    business_id: str,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    db: AsyncSession = Depends(get_db)
):
    """Get call analytics for a business."""
    try:
        call_service = CallSessionService(db)
        
        analytics = await call_service.get_call_analytics(
            business_id=business_id,
            date_from=date_from,
            date_to=date_to
        )
        
        return analytics
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/webhook/vapi")
async def vapi_webhook(
    request: dict,
    db: AsyncSession = Depends(get_db)
):
    """Webhook endpoint for Vapi.ai events."""
    try:
        event_type = request.get("message", {}).get("type")
        
        if event_type == "assistant-request":
            return {
                "assistant": {
                    "firstMessage": "Welcome to Demo Hotel! How can I help you today?",
                    "model": {
                        "provider": "openai",
                        "model": "gpt-4o-mini",
                        "messages": [
                            {
                                "role": "system",
                                "content": """You are Aida, a friendly booking assistant for Demo Hotel.
Help customers with bookings, status checks, cancellations, and rescheduling.
Available rooms: Deluxe Room (6000 BDT), Premium Suite (12000 BDT), Family Room (9000 BDT).
Keep responses SHORT (1-2 sentences for voice).
If customer wants human, say "Press 0 to speak with a representative."
"""
                            }
                        ]
                    },
                    "voice": {
                        "provider": "11labs",
                        "voiceId": "21m00Tcm4TlvDq8ikWAM"
                    }
                }
            }
        
        elif event_type == "end-of-call-report":
            call_service = CallSessionService(db)
            
            call_id = request.get("message", {}).get("call", {}).get("id")
            transcript = request.get("message", {}).get("transcript", "")
            
            if call_id:
                call = await call_service.get_call_by_provider_id(call_id)
                if call:
                    await call_service.update_transcript(
                        call_session_id=call["call_session_id"],
                        transcript=transcript
                    )
                    await call_service.end_call(
                        call_session_id=call["call_session_id"],
                        status="COMPLETED",
                        resolution_type="AI_RESOLVED"
                    )
            
            return {"status": "received"}
        
        return {"status": "ok"}
        
    except Exception as e:
        return {"status": "error", "message": str(e)}