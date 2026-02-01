from typing import TypedDict


class BookingState(TypedDict, total=False):
    """
    State that persists throughout a booking conversation.
    LangGraph passes this state between nodes, and each node can read/update it.
    """
    
    # === Conversation identifiers ===
    conversation_id: str
    business_id: str
    business_slug: str
    
    # === Conversation context ===
    messages: list[dict]
    current_message: str
    
    # === Business information (loaded from database) ===
    business_name: str
    ai_agent_name: str
    ai_tone: str
    available_services: list[dict]
    
    # === Extracted from conversation ===
    selected_service_id: str | None
    selected_service_name: str | None
    selected_slot_start: str | None
    selected_slot_end: str | None
    customer_name: str | None
    customer_phone: str | None
    customer_email: str | None
    
# === Booking tracking ===
    booking_id: str | None
    public_tracking_id: str | None
    booking_status: str
    mentioned_booking_id: str | None      # Booking ID user mentioned (for status check, cancel)
    
    # === Slot availability ===
    slot_unavailable: bool
    slot_alternatives: list[dict]
    
    # === Handoff (escalation) tracking ===
    needs_escalation: bool
    handoff_id: str | None
    handoff_ticket_id: str | None
    
    # === Control flow ===
    parsed_intent: str
    next_action: str
    current_flow: str | None        # 'booking', 'cancellation', 'rescheduling', 'status_check'
    response: str
    
    # === Error handling ===
    error: str | None