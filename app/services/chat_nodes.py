from app.services.chat_state import BookingState
from app.services.llm import extract_json_from_llm, call_llm_with_history


# ============== NODE 1: Parse user message ==============

async def parse_message_node(state: BookingState) -> BookingState:
    """
    Extract intent and entities from the user's message.
    This node runs first for every user message.
    """
    from datetime import datetime, timedelta
    
    # Get current date info for proper date parsing
    today = datetime.now()
    tomorrow = today + timedelta(days=1)
    
    # Calculate next week days
    days_of_week = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    current_day_name = days_of_week[today.weekday()]
    
    date_context = f"""
Current date/time information (USE THIS FOR DATE PARSING):
- Today is: {current_day_name}, {today.strftime('%B %d, %Y')}
- Today's date: {today.strftime('%Y-%m-%d')}
- Tomorrow's date: {tomorrow.strftime('%Y-%m-%d')}
- Current time: {today.strftime('%H:%M')}

When user says:
- "today" = {today.strftime('%Y-%m-%d')}
- "tomorrow" = {tomorrow.strftime('%Y-%m-%d')}
- "next Monday" = calculate from today's date
- "this weekend" = the upcoming Saturday/Sunday
"""

    services_list = state.get("available_services", [])
    services_names = [s["service_name"] for s in services_list] if services_list else []

    system_prompt = f"""You are an intent and entity extractor for a booking chatbot.

{date_context}

Available services at this business: {services_names}

Analyze the user's message and extract:
1. intent: What does the user want to do?
2. entities: What specific information did they provide?

Respond with JSON only:
{{
    "intent": "greet" | "list_services" | "select_service" | "ask_service_details" | "select_slot" | "provide_contact" | "confirm_booking" | "complete_booking" | "check_status" | "cancel_booking" | "confirm_cancel" | "reschedule" | "escalate" | "cancel" | "other",
    "service_mentioned": "service name if mentioned, or null",
    "date_mentioned": "date if mentioned (YYYY-MM-DD format based on current date above), or null",
    "time_mentioned": "time if mentioned (HH:MM 24hr format), or null",
    "contact_info": {{
        "name": "name if provided, or null",
        "phone": "phone if provided, or null",
        "email": "email if provided, or null"
    }},
    "wants_human": true if user wants to talk to a human/agent/person, false otherwise,
    "booking_id_mentioned": "booking/tracking ID if mentioned (like BK-XXXXXX), or null"
}}

Intent definitions:
- greet: Hello, hi, good morning, etc.
- list_services: User wants to see what services are available
- select_service: User is choosing/mentioning a specific service
- ask_service_details: User wants more info about a service
- select_slot: User is choosing a time/date
- provide_contact: User is giving their name, phone, or email
- complete_booking: User provides ALL booking info at once (service + date/time + contact info in one message)
- check_status: User wants to check existing booking status
- cancel_booking: User EXPLICITLY wants to cancel (says "cancel my booking", "I want to cancel")
- confirm_cancel: User confirms cancellation AFTER being asked "are you sure you want to cancel?"
- reschedule: User wants to change their booking time
- escalate: User wants to talk to a human/agent/real person
- cancel: User wants to stop the current conversation (NOT booking cancellation)
- other: Doesn't fit above categories

CRITICAL RULES:
1. If user says "yes", "confirm", "correct", "proceed" WITHOUT mentioning "cancel" → use "confirm_booking"
2. Only use "confirm_cancel" if the previous message asked about cancellation
3. Only use "cancel_booking" if user explicitly says "cancel my booking" or similar
4. When in doubt between confirm_booking and confirm_cancel, prefer "confirm_booking"IMPORTANT: If the conversation context shows the user was just asked to confirm a cancellation, and they respond with "yes", "confirm", "go ahead", etc., use "confirm_cancel" NOT "cancel".
"""

    current_msg = state.get("current_message", "")

    extracted = await extract_json_from_llm(system_prompt, current_msg)

    # Update state with extracted information
    state["parsed_intent"] = extracted.get("intent", "other")

    if extracted.get("service_mentioned"):
        # Find service ID from name
        for svc in services_list:
            if svc["service_name"].lower() == extracted["service_mentioned"].lower():
                state["selected_service_id"] = svc["id"]
                state["selected_service_name"] = svc["service_name"]
                break

    if extracted.get("date_mentioned") and extracted.get("time_mentioned"):
        state["selected_slot_start"] = f"{extracted['date_mentioned']}T{extracted['time_mentioned']}:00"
    elif extracted.get("date_mentioned"):
        # Date without time - store just the date for now
        state["selected_slot_start"] = f"{extracted['date_mentioned']}T12:00:00"

    contact = extracted.get("contact_info", {})
    if contact.get("name"):
        state["customer_name"] = contact["name"]
    if contact.get("phone"):
        state["customer_phone"] = contact["phone"]
    if contact.get("email"):
        state["customer_email"] = contact["email"]

    if extracted.get("wants_human"):
        state["needs_escalation"] = True
    
    # Store booking ID if mentioned (for status check, cancel, reschedule)
    if extracted.get("booking_id_mentioned"):
        state["mentioned_booking_id"] = extracted["booking_id_mentioned"]

    return state

# ============== NODE 2: Router (decides next step) ==============
def route_after_parse(state: BookingState) -> str:
    """
    Conditional edge function - decides which node to go to next.
    Returns the name of the next node.
    """
    
    intent = state.get("parsed_intent", "other")
    
    # Check for escalation first
    if state.get("needs_escalation"):
        return "escalate_node"
    
    # Route based on intent
    if intent == "greet":
        return "greet_node"
    
    if intent == "list_services":
        return "list_services_node"
    
    if intent == "select_service":
        return "handle_service_selection_node"
    
    if intent == "ask_service_details":
        return "show_service_details_node"
    
    if intent == "select_slot":
        return "handle_slot_selection_node"
    
    if intent == "provide_contact":
        return "handle_contact_node"
    
    if intent == "confirm_booking":
        return "confirm_booking_node"
    
    if intent == "complete_booking":
        return "confirm_booking_node"
    
    if intent == "check_status":
        return "check_status_node"
    
    if intent == "cancel_booking":
        return "cancel_booking_node"
    
    if intent == "confirm_cancel":
        return "confirm_cancel_node"
    
    if intent == "reschedule":
        return "reschedule_node"
    
    if intent == "escalate":
        return "escalate_node"
    
    # Default: generate a helpful response
    return "general_response_node"
# ============== NODE 3: Greet ==============

async def greet_node(state: BookingState) -> BookingState:
    """Handle greetings and introduce the assistant."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    business_name = state.get("business_name", "our business")
    tone = state.get("ai_tone", "friendly and professional")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.
    
The user just greeted you. Respond with a warm greeting and ask how you can help them today.
Mention that you can help them book services, check availability, or answer questions.

Keep your response brief (2-3 sentences max)."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 4: List Services ==============

async def list_services_node(state: BookingState) -> BookingState:
    """Show available services to the user."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    business_name = state.get("business_name", "our business")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])
    
    services_text = "\n".join([
        f"- {s['service_name']}: {s.get('description', 'No description')} - {s.get('base_price', 'Price varies')} {s.get('currency', '')}"
        for s in services
    ]) if services else "No services currently available."
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.

The user wants to see available services. Here are the services:

{services_text}

Present these services in a friendly way and ask which one they'd like to book.
Keep your response concise but informative."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 5: Handle Service Selection ==============

async def handle_service_selection_node(state: BookingState) -> BookingState:
    """User selected a service - acknowledge and ask for preferred time."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    service_name = state.get("selected_service_name", "the service")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user has selected: {service_name}

Confirm their selection and ask when they would like to book.
Ask for their preferred date and time.
Keep your response brief (2-3 sentences)."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_slot_selection"
    return state


# ============== NODE 6: Handle Slot Selection ==============

async def handle_slot_selection_node(state: BookingState) -> BookingState:
    """User provided time preference - acknowledge and ask for contact info."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    slot = state.get("selected_slot_start", "the selected time")
    service_name = state.get("selected_service_name", "the service")
    
    # Check if we have service selected
    if not state.get("selected_service_id"):
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user mentioned a time but hasn't selected a service yet.
Politely ask them which service they'd like to book first."""
        
        messages = state.get("messages", [])
        response = await call_llm_with_history(system_prompt, messages)
        state["response"] = response
        return state
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to book {service_name} at {slot}.

Confirm the time and ask for their contact information:
- Full name
- Phone number
- Email address

Keep your response brief and friendly."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_contact_info"
    return state


# ============== NODE 7: Handle Contact Info ==============

async def handle_contact_node(state: BookingState) -> BookingState:
    """User provided contact info - check if complete and proceed to confirmation."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    
    name = state.get("customer_name")
    phone = state.get("customer_phone")
    email = state.get("customer_email")
    
    missing = []
    if not name:
        missing.append("name")
    if not phone:
        missing.append("phone number")
    if not email:
        missing.append("email address")
    
    if missing:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user provided some contact information, but we still need: {', '.join(missing)}.

Politely ask for the missing information.
Keep your response brief."""
        
        messages = state.get("messages", [])
        response = await call_llm_with_history(system_prompt, messages)
        state["response"] = response
        return state
    
    # All contact info collected - summarize and ask for confirmation
    service_name = state.get("selected_service_name", "the service")
    slot = state.get("selected_slot_start", "the selected time")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user has provided all information for their booking:
- Service: {service_name}
- Time: {slot}
- Name: {name}
- Phone: {phone}
- Email: {email}

Summarize the booking details and ask them to confirm.
Let them know that after confirmation, they will receive a payment link.
Keep your response clear and professional."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_confirmation"
    return state


# ============== NODE 8: Confirm Booking ==============

async def confirm_booking_node(state: BookingState) -> BookingState:
    """User confirmed - create booking and provide tracking ID."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    
    # Check if we have all required info
    if not all([
        state.get("selected_service_id"),
        state.get("selected_slot_start"),
        state.get("customer_name"),
        state.get("customer_phone"),
        state.get("customer_email")
    ]):
        state["response"] = "I don't have all the information needed to complete your booking. Let me help you provide the missing details."
        return state
    
    # Note: Actual booking creation will happen in the service layer
    # For now, we just prepare the response
    tracking_id = state.get("public_tracking_id", "PENDING")
    service_name = state.get("selected_service_name", "the service")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The booking has been created successfully!
- Service: {service_name}
- Tracking ID: {tracking_id}

Congratulate the user and let them know:
1. They will receive a payment link shortly
2. They can use the tracking ID to check their booking status
3. Thank them for choosing the business

Keep your response warm and professional."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["booking_status"] = "CONTACT_COLLECTED"
    return state


# ============== NODE 9: Escalate to Human ==============

async def escalate_node(state: BookingState) -> BookingState:
    """User wants to talk to a human."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to speak with a human team member.

Let them know:
1. You understand they'd prefer to speak with a person
2. Ask for their contact information (name, phone, email) if not already provided
3. A team member will reach out to them shortly
4. They will receive a ticket ID for reference

Be empathetic and helpful."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["needs_escalation"] = True
    return state


# ============== NODE 10: General Response ==============

async def general_response_node(state: BookingState) -> BookingState:
    """Handle general queries or unclear intents."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    business_name = state.get("business_name", "our business")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])
    
    services_names = [s["service_name"] for s in services] if services else []
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant for {business_name}.

Available services: {services_names}

The user's message didn't clearly match a specific action. 
Respond helpfully based on the conversation context.
If unsure what they need, politely ask for clarification.
Remind them you can help with:
- Booking services
- Checking availability
- Answering questions about services
- Connecting them with a human if needed

Keep your response brief and helpful."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 11: Show Service Details ==============

async def show_service_details_node(state: BookingState) -> BookingState:
    """Show detailed information about a service."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    services = state.get("available_services", [])
    service_name = state.get("selected_service_name")
    
    # Find the service details
    service_details = None
    for s in services:
        if s.get("service_name", "").lower() == (service_name or "").lower():
            service_details = s
            break
    
    if service_details:
        details_text = f"""
Service: {service_details.get('service_name')}
Description: {service_details.get('description', 'No description available')}
Price: {service_details.get('base_price', 'Price varies')} {service_details.get('currency', '')}
Duration: {service_details.get('duration_minutes', 'Varies')} minutes
"""
    else:
        details_text = "I couldn't find details for that service."
    
    system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

Here are the service details:
{details_text}

Present this information in a friendly way and ask if they'd like to book this service.
Keep your response informative but concise."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state


# ============== NODE 12: Check Booking Status ==============

async def check_status_node(state: BookingState) -> BookingState:
    """Handle booking status check requests."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    
    # If user provided a booking ID, we'll look it up
    if mentioned_booking_id:
        # The actual lookup will happen in chat_service
        # For now, just acknowledge we have the ID
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to check their booking status and provided tracking ID: {mentioned_booking_id}

Let them know you're looking up their booking and will provide the details shortly.
Keep your response brief."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to check their booking status but hasn't provided a tracking ID.

Ask them for their booking tracking ID (it looks like BK-XXXXXX).
Let them know you'll look up their booking once they provide the ID.

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state

# ============== NODE 13: Cancel Booking ==============

async def cancel_booking_node(state: BookingState) -> BookingState:
    """Handle booking cancellation requests."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    current_booking_id = state.get("public_tracking_id")
    
    # Check if we have a booking to cancel
    booking_id = mentioned_booking_id or current_booking_id
    
    if booking_id:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to cancel their booking (ID: {booking_id}).

Ask them to confirm they want to cancel this booking.
Let them know that cancellation cannot be undone.

Keep your response brief and empathetic."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to cancel a booking but hasn't specified which one.

Ask them for their booking tracking ID (it looks like BK-XXXXXX).

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_cancel_confirmation"
    return state


# ============== NODE 14: Reschedule Booking ==============

async def reschedule_node(state: BookingState) -> BookingState:
    """Handle booking rescheduling requests."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    current_booking_id = state.get("public_tracking_id")
    current_slot = state.get("selected_slot_start")
    
    # Check if we have a booking to reschedule
    booking_id = mentioned_booking_id or current_booking_id
    
    if booking_id:
        if current_slot:
            system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to reschedule their booking (ID: {booking_id}).
Current appointment time: {current_slot}

Ask them when they would like to reschedule to.
Request their preferred new date and time.

Keep your response brief and helpful."""
        else:
            system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to reschedule their booking (ID: {booking_id}).

Ask them when they would like to reschedule to.
Request their preferred new date and time.

Keep your response brief and helpful."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user wants to reschedule a booking but hasn't specified which one.

Ask them for their booking tracking ID (it looks like BK-XXXXXX).

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    state["next_action"] = "await_new_slot"
    return state

# ============== NODE 15: Confirm Cancel ==============

async def confirm_cancel_node(state: BookingState) -> BookingState:
    """Handle confirmed booking cancellation."""
    
    agent_name = state.get("ai_agent_name", "Assistant")
    tone = state.get("ai_tone", "friendly and professional")
    mentioned_booking_id = state.get("mentioned_booking_id")
    current_booking_id = state.get("public_tracking_id")
    
    booking_id = mentioned_booking_id or current_booking_id
    
    if booking_id:
        # The actual cancellation will happen in chat_service._handle_special_intents
        state["cancel_confirmed"] = True
        state["booking_to_cancel"] = booking_id
        
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user has confirmed they want to cancel booking {booking_id}.
Acknowledge that the booking is being cancelled.

Keep your response brief and empathetic."""
    else:
        system_prompt = f"""You are {agent_name}, a {tone} booking assistant.

The user confirmed cancellation but we don't have a booking ID.
Ask them for the booking tracking ID.

Keep your response brief."""
    
    messages = state.get("messages", [])
    response = await call_llm_with_history(system_prompt, messages)
    
    state["response"] = response
    return state