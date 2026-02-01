import uuid
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models import (
    Business,
    Service,
    Conversation,
    ConversationMessage,
    BusinessAISettings,
    Booking,
)
from app.services.chat_state import BookingState
from app.services.chat_graph import booking_graph
from app.services.booking_service import BookingService
from app.services.slot_service import SlotService
from app.services.handoff_service import HandoffService


class ChatService:
    """
    Service that connects LangGraph to the database.
    Includes booking state persistence, slot availability checking, and escalation handling.
    """
    
    def __init__(self, db: AsyncSession):
        self.db = db
        self.booking_service = BookingService(db)
        self.slot_service = SlotService(db)
        self.handoff_service = HandoffService(db)
    
    async def start_conversation(
        self,
        business_slug: str,
        user_session_id: str | None = None,
        channel: str = "CHAT"
    ) -> dict:
        """Start a new conversation for a business."""
        
        result = await self.db.execute(
            select(Business).where(Business.slug == business_slug)
        )
        business = result.scalar_one_or_none()
        
        if not business:
            raise ValueError(f"Business not found: {business_slug}")
        
        conversation = Conversation(
            business_id=business.id,
            channel=channel,
            status="STARTED",
            user_session_id=user_session_id,
            started_at=datetime.utcnow(),
        )
        self.db.add(conversation)
        await self.db.flush()
        
        business_info = await self._load_business_info(business.id)
        
        await self.db.commit()
        
        return {
            "conversation_id": str(conversation.id),
            "business_id": str(business.id),
            "business_name": business.business_name,
            **business_info
        }
    
    async def _load_business_info(self, business_id: uuid.UUID) -> dict:
        """Load business info for the chatbot."""
        
        result = await self.db.execute(
            select(BusinessAISettings).where(
                BusinessAISettings.business_id == business_id
            )
        )
        ai_settings = result.scalar_one_or_none()
        
        result = await self.db.execute(
            select(Service).where(
                Service.business_id == business_id,
                Service.is_active == True
            )
        )
        services = result.scalars().all()
        
        services_list = [
            {
                "id": str(s.id),
                "service_name": s.service_name,
                "description": s.description,
                "base_price": float(s.base_price) if s.base_price else None,
                "currency": s.currency,
                "duration_minutes": s.duration_minutes,
            }
            for s in services
        ]
        
        return {
            "ai_agent_name": ai_settings.agent_name if ai_settings else "Assistant",
            "ai_tone": ai_settings.tone_of_voice if ai_settings else "friendly and professional",
            "available_services": services_list,
        }
    
    async def send_message(
        self,
        conversation_id: str,
        user_message: str
    ) -> dict:
        """Process a user message and get AI response with booking state persistence."""
        
        conv_uuid = uuid.UUID(conversation_id)
        
        # Load conversation
        result = await self.db.execute(
            select(Conversation).where(Conversation.id == conv_uuid)
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")
        
        # Load conversation history
        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == conv_uuid)
            .order_by(ConversationMessage.created_at)
        )
        history = result.scalars().all()
        
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in history
        ]
        
        # Load business info
        business_info = await self._load_business_info(conversation.business_id)
        
        result = await self.db.execute(
            select(Business).where(Business.id == conversation.business_id)
        )
        business = result.scalar_one()
        
        # Load existing booking for this conversation (STATE PERSISTENCE)
        existing_booking = await self.booking_service.get_booking_by_conversation(conversation_id)
        
        # Load existing handoff if any
        existing_handoff = await self.handoff_service.get_handoff_by_conversation(conversation_id)
        
        # Save user message
        user_msg_record = ConversationMessage(
            business_id=conversation.business_id,
            conversation_id=conv_uuid,
            role="user",
            content=user_message,
            created_at=datetime.utcnow(),
        )
        self.db.add(user_msg_record)
        
        messages.append({"role": "user", "content": user_message})
        
        # Build state for LangGraph - include existing booking data
        state: BookingState = {
            "conversation_id": conversation_id,
            "business_id": str(conversation.business_id),
            "business_name": business.business_name,
            "messages": messages,
            "current_message": user_message,
            "ai_agent_name": business_info["ai_agent_name"],
            "ai_tone": business_info["ai_tone"],
            "available_services": business_info["available_services"],
            "needs_escalation": False,
            "slot_unavailable": False,
            "slot_alternatives": [],
            "current_flow": None,
        }
        
        # Add existing booking data to state if exists
        if existing_booking:
            state["booking_id"] = existing_booking["booking_id"]
            state["public_tracking_id"] = existing_booking["public_tracking_id"]
            state["selected_service_id"] = existing_booking["service_id"]
            state["selected_service_name"] = existing_booking["service_name"]
            state["selected_slot_start"] = existing_booking["slot_start"]
            state["selected_slot_end"] = existing_booking["slot_end"]
            state["customer_name"] = existing_booking["customer_name"]
            state["customer_phone"] = existing_booking["customer_phone"]
            state["customer_email"] = existing_booking["customer_email"]
            state["booking_status"] = existing_booking["status"]
            state["current_flow"] = "booking"
        
        # Add existing handoff data to state if exists
        if existing_handoff:
            state["handoff_id"] = existing_handoff["handoff_id"]
            state["handoff_ticket_id"] = existing_handoff["public_ticket_id"]
        
        # Run LangGraph
        result_state = await booking_graph.ainvoke(state)
        
        # Handle special intents that need database lookups
        await self._handle_special_intents(state, result_state)
        
        # Handle booking actions based on what LangGraph extracted
        await self._handle_booking_actions(conversation_id, str(conversation.business_id), state, result_state)
        
        # Check if slot was unavailable and modify response
        ai_response = result_state.get("response", "I'm sorry, I couldn't process that.")
        
        if result_state.get("slot_unavailable"):
            alternatives = result_state.get("slot_alternatives", [])
            if alternatives:
                alt_text = "\n".join([f"- {alt['start']}" for alt in alternatives[:5]])
                ai_response = f"I'm sorry, that time slot is no longer available. Here are some alternative times:\n{alt_text}\n\nWhich one would you prefer?"
            else:
                ai_response = "I'm sorry, that time slot is no longer available. Could you please suggest another time?"
        
        # Check if escalation was created and modify response
        if result_state.get("handoff_ticket_id") and not existing_handoff:
            ticket_id = result_state.get("handoff_ticket_id")
            ai_response = f"I've created a support ticket for you. Your ticket ID is **{ticket_id}**. A team member will contact you shortly at the phone number or email you provided. Thank you for your patience!"
        
        # Save AI response
        ai_msg_record = ConversationMessage(
            business_id=conversation.business_id,
            conversation_id=conv_uuid,
            role="assistant",
            content=ai_response,
            created_at=datetime.utcnow(),
        )
        self.db.add(ai_msg_record)
        
        # Update conversation
        conversation.last_message_at = datetime.utcnow()
        if not result_state.get("needs_escalation"):
            conversation.status = "IN_PROGRESS"
        
        await self.db.commit()
        
        # Get updated booking info
        updated_booking = await self.booking_service.get_booking_by_conversation(conversation_id)
        updated_handoff = await self.handoff_service.get_handoff_by_conversation(conversation_id)
        
        return {
            "conversation_id": conversation_id,
            "response": ai_response,
            "intent": result_state.get("parsed_intent"),
            "needs_escalation": result_state.get("needs_escalation", False),
            "selected_service": result_state.get("selected_service_name"),
            "selected_slot": result_state.get("selected_slot_start"),
            "booking_id": updated_booking["booking_id"] if updated_booking else None,
            "public_tracking_id": updated_booking["public_tracking_id"] if updated_booking else None,
            "booking_status": updated_booking["status"] if updated_booking else None,
            "slot_unavailable": result_state.get("slot_unavailable", False),
            "slot_alternatives": result_state.get("slot_alternatives", []),
            "handoff_ticket_id": updated_handoff["public_ticket_id"] if updated_handoff else None,
        }
    
    async def _handle_special_intents(
        self,
        old_state: BookingState,
        result_state: BookingState
    ) -> None:
        """
        Handle intents that need database lookups.
        Updates result_state with actual data from database.
        """
        
        intent = result_state.get("parsed_intent")
        mentioned_booking_id = result_state.get("mentioned_booking_id") or old_state.get("mentioned_booking_id")
        
        # Handle booking status check
        if intent == "check_status" and mentioned_booking_id:
            booking_info = await self.booking_service.get_booking_by_tracking_id(mentioned_booking_id)
            
            if booking_info:
                result_state["response"] = f"""Here are the details for booking **{mentioned_booking_id}**:

- **Service:** {booking_info['service_name']}
- **Status:** {booking_info['status']}
- **Date/Time:** {booking_info['slot_start'] or 'Not scheduled yet'}
- **Customer:** {booking_info['customer_name'] or 'Not provided'}
- **Payment:** {booking_info['payment_status']}

Is there anything else I can help you with?"""
            else:
                result_state["response"] = f"I couldn't find a booking with tracking ID **{mentioned_booking_id}**. Please double-check the ID and try again. The format should be like BK-XXXXXX."
        
        # Handle booking cancellation confirmation
        if intent == "confirm_cancel":
            tracking_id = mentioned_booking_id or old_state.get("public_tracking_id") or result_state.get("booking_to_cancel")
            if tracking_id:
                try:
                    cancel_result = await self.booking_service.cancel_booking_by_tracking_id(tracking_id)
                    result_state["response"] = f"Your booking **{tracking_id}** has been successfully cancelled. If you'd like to make a new booking, just let me know!"
                    result_state["booking_status"] = "CANCELLED"
                except ValueError as e:
                    result_state["response"] = f"I couldn't cancel the booking: {str(e)}"
            else:
                result_state["response"] = "I don't have a booking ID to cancel. Could you please provide your booking tracking ID (like BK-XXXXXX)?"
        
        # Handle rescheduling
        if intent == "reschedule" and mentioned_booking_id:
            new_slot = result_state.get("selected_slot_start")
            if new_slot:
                try:
                    slot_start = datetime.fromisoformat(new_slot.replace("Z", "+00:00")) if "T" in new_slot else datetime.fromisoformat(new_slot)
                    slot_end = slot_start + timedelta(hours=1)
                    
                    reschedule_result = await self.booking_service.reschedule_booking_by_tracking_id(
                        tracking_id=mentioned_booking_id,
                        new_slot_start=slot_start,
                        new_slot_end=slot_end
                    )
                    result_state["response"] = f"Your booking **{mentioned_booking_id}** has been rescheduled to **{slot_start.strftime('%B %d, %Y at %I:%M %p')}**. Is there anything else I can help you with?"
                    result_state["booking_status"] = "RESCHEDULED"
                except ValueError as e:
                    result_state["response"] = f"I couldn't reschedule the booking: {str(e)}"
    
    async def _handle_booking_actions(
        self,
        conversation_id: str,
        business_id: str,
        old_state: BookingState,
        new_state: BookingState
    ) -> None:
        """
        Handle booking creation, updates, and escalation based on conversation progress.
        Includes slot availability checking and handoff creation.
        
        IMPROVED: Handles multi-info messages (service + slot + contact in one message)
        """
        
        intent = new_state.get("parsed_intent")
        
        # Step 1: Create booking if service selected and no booking exists
        if (new_state.get("selected_service_id") and not old_state.get("booking_id")):
            booking = await self.booking_service.create_booking(
                business_id=business_id,
                service_id=new_state["selected_service_id"],
                conversation_id=conversation_id
            )
            new_state["booking_id"] = booking["booking_id"]
            new_state["public_tracking_id"] = booking["public_tracking_id"]
            new_state["current_flow"] = "booking"
        
        booking_id = new_state.get("booking_id") or old_state.get("booking_id")
        
        # Step 2: Update slot if provided (and different from existing)
        if (new_state.get("selected_slot_start") and 
            new_state.get("selected_slot_start") != old_state.get("selected_slot_start") and
            intent not in ["reschedule"]):
            
            try:
                slot_start_str = new_state["selected_slot_start"]
                if "T" in slot_start_str:
                    slot_start = datetime.fromisoformat(slot_start_str.replace("Z", "+00:00"))
                else:
                    slot_start = datetime.fromisoformat(slot_start_str)
                
                slot_end = slot_start + timedelta(hours=1)
                service_id = new_state.get("selected_service_id") or old_state.get("selected_service_id")
                
                if service_id and booking_id:
                    slot_check = await self.slot_service.validate_and_reserve_slot(
                        service_id=service_id,
                        slot_start=slot_start,
                        slot_end=slot_end
                    )
                    
                    if slot_check["available"]:
                        await self.booking_service.update_slot(
                            booking_id=booking_id,
                            slot_start=slot_start,
                            slot_end=slot_end
                        )
                        new_state["booking_status"] = "SLOT_SELECTED"
                    else:
                        new_state["slot_unavailable"] = True
                        new_state["slot_alternatives"] = slot_check.get("alternatives", [])
                        new_state["selected_slot_start"] = None
                        
            except (ValueError, TypeError):
                pass
        
        # Step 3: Update contact if ALL contact fields provided
        new_name = new_state.get("customer_name")
        new_phone = new_state.get("customer_phone")
        new_email = new_state.get("customer_email")
        
        if booking_id and all([new_name, new_phone, new_email]):
            old_name = old_state.get("customer_name")
            old_phone = old_state.get("customer_phone")
            old_email = old_state.get("customer_email")
            
            if (new_name != old_name or new_phone != old_phone or new_email != old_email):
                await self.booking_service.update_contact(
                    booking_id=booking_id,
                    customer_name=new_name,
                    customer_phone=new_phone,
                    customer_email=new_email
                )
                new_state["booking_status"] = "CONTACT_COLLECTED"
        
        # Step 4: Auto-confirm if all data present AND intent is confirm
        # OR if all data was provided in a single message
        if booking_id:
            booking = await self.booking_service.get_booking(booking_id)
            
            if booking:
                has_service = booking.get("service_id") is not None
                has_slot = booking.get("slot_start") is not None
                has_contact = all([
                    booking.get("customer_name"),
                    booking.get("customer_phone"),
                    booking.get("customer_email")
                ])
                
                # Confirm if:
                # 1. Intent is confirm_booking AND status is CONTACT_COLLECTED
                # 2. OR all data provided in one message (multi-info scenario)
                all_data_in_one_message = (
                    new_state.get("selected_service_id") and
                    new_state.get("selected_slot_start") and
                    new_state.get("customer_name") and
                    new_state.get("customer_phone") and
                    new_state.get("customer_email") and
                    not old_state.get("booking_id")
                )
                
                should_confirm = (
                    (intent == "confirm_booking" and booking["status"] == "CONTACT_COLLECTED") or
                    (intent == "complete_booking" and has_service and has_slot and has_contact) or
                    (all_data_in_one_message and has_service and has_slot and has_contact)
                )
                
                if should_confirm and booking["status"] != "CONFIRMED":
                    await self.booking_service.confirm_booking(booking_id)
                    new_state["booking_status"] = "CONFIRMED"
        
        # Step 5: Handle escalation to human
        if new_state.get("needs_escalation") and not old_state.get("handoff_id"):
            contact_name = new_state.get("customer_name") or old_state.get("customer_name")
            contact_phone = new_state.get("customer_phone") or old_state.get("customer_phone")
            contact_email = new_state.get("customer_email") or old_state.get("customer_email")
            
            if contact_name or contact_phone or contact_email:
                handoff = await self.handoff_service.create_handoff(
                    business_id=business_id,
                    conversation_id=conversation_id,
                    reason="User requested human assistance",
                    contact_name=contact_name,
                    contact_phone=contact_phone,
                    contact_email=contact_email,
                    booking_id=booking_id
                )
                new_state["handoff_id"] = handoff["handoff_id"]
                new_state["handoff_ticket_id"] = handoff["public_ticket_id"]
    
    async def get_conversation(self, conversation_id: str) -> dict | None:
        """Get conversation details."""
        
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id)
            )
        )
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            return None
        
        return {
            "id": str(conversation.id),
            "business_id": str(conversation.business_id),
            "channel": conversation.channel,
            "status": conversation.status,
            "resolution_type": conversation.resolution_type,
            "outcome": conversation.outcome,
            "started_at": conversation.started_at.isoformat() if conversation.started_at else None,
            "last_message_at": conversation.last_message_at.isoformat() if conversation.last_message_at else None,
        }
    
    async def get_conversation_history(self, conversation_id: str) -> list[dict]:
        """Get all messages in a conversation."""
        
        result = await self.db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.conversation_id == uuid.UUID(conversation_id))
            .order_by(ConversationMessage.created_at)
        )
        messages = result.scalars().all()
        
        return [
            {
                "id": str(msg.id),
                "role": msg.role,
                "content": msg.content,
                "created_at": msg.created_at.isoformat() if msg.created_at else None,
            }
            for msg in messages
        ]
    
    async def end_conversation(
        self,
        conversation_id: str,
        resolution_type: str,
        outcome: str
    ) -> None:
        """Mark a conversation as ended."""
        
        result = await self.db.execute(
            select(Conversation).where(
                Conversation.id == uuid.UUID(conversation_id)
            )
        )
        conversation = result.scalar_one_or_none()
        
        if conversation:
            conversation.status = "RESOLVED"
            conversation.resolution_type = resolution_type
            conversation.outcome = outcome
            conversation.resolved_at = datetime.utcnow()
            conversation.closed_at = datetime.utcnow()
            await self.db.commit()