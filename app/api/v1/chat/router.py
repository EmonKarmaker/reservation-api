from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.services.chat_service import ChatService
from app.schemas.conversation import (
    ConversationStart,
    ConversationResponse,
    ChatRequest,
    ChatResponse,
)

router = APIRouter(prefix="/chat", tags=["Chat"])


# ==================== START CONVERSATION ====================

@router.post("/conversations", response_model=dict)
async def start_conversation(
    request: ConversationStart,
    db: AsyncSession = Depends(get_db)
):
    """
    Start a new chat conversation with a business.
    
    This is the first endpoint called when a user opens the chatbot.
    
    Request body:
    - business_slug: The URL-friendly identifier of the business (e.g., "cool-salon")
    - user_session_id: Optional browser session ID to identify returning users
    
    Returns:
    - conversation_id: Unique ID for this conversation (use in subsequent messages)
    - business_id: ID of the business
    - business_name: Display name of the business
    - ai_agent_name: Name of the AI assistant
    - available_services: List of services offered
    
    Example:
        POST /api/v1/chat/conversations
        {"business_slug": "cool-salon"}
        
        Response:
        {
            "conversation_id": "uuid-here",
            "business_name": "Cool Salon",
            "ai_agent_name": "Sara",
            "available_services": [...]
        }
    """
    try:
        chat_service = ChatService(db)
        result = await chat_service.start_conversation(
            business_slug=request.business_slug,
            user_session_id=request.user_session_id,
            channel="CHAT"
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


# ==================== SEND MESSAGE ====================

@router.post("/conversations/{conversation_id}/messages", response_model=ChatResponse)
async def send_message(
    conversation_id: str,
    request: ChatRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Send a message in an existing conversation and get AI response.
    
    This is the main endpoint for chatbot interaction.
    
    Path parameters:
    - conversation_id: The UUID returned from start_conversation
    
    Request body:
    - message: The user's message text
    
    Returns:
    - conversation_id: Same as input
    - message: AI's response
    - intent: What the AI understood (greet, select_service, etc.)
    - booking_id: If a booking was created
    - needs_escalation: True if user wants to talk to human
    
    Example:
        POST /api/v1/chat/conversations/uuid-here/messages
        {"message": "I want to book a haircut"}
        
        Response:
        {
            "conversation_id": "uuid-here",
            "message": "Great choice! When would you like to come in?",
            "intent": "select_service",
            "booking_id": null,
            "needs_escalation": false
        }
    """
    try:
        chat_service = ChatService(db)
        result = await chat_service.send_message(
            conversation_id=conversation_id,
            user_message=request.message
        )
        
        return ChatResponse(
            conversation_id=result["conversation_id"],
            message=result["response"],
            intent=result.get("intent"),
            booking_id=None,  # Will be added when booking service is built
            requires_action=None,
            available_slots=None,
            service_options=None,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing message: {str(e)}"
        )


# ==================== GET CONVERSATION ====================

@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get details of a conversation.
    
    Path parameters:
    - conversation_id: The UUID of the conversation
    
    Returns:
    - Conversation details (status, timestamps, etc.)
    """
    chat_service = ChatService(db)
    result = await chat_service.get_conversation(conversation_id)
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    return result


# ==================== GET CONVERSATION HISTORY ====================

@router.get("/conversations/{conversation_id}/messages")
async def get_conversation_history(
    conversation_id: str,
    db: AsyncSession = Depends(get_db)
):
    """
    Get all messages in a conversation.
    
    Use this to display chat history when user returns to a conversation.
    
    Path parameters:
    - conversation_id: The UUID of the conversation
    
    Returns:
    - List of messages with role (user/assistant) and content
    """
    chat_service = ChatService(db)
    
    # First check if conversation exists
    conversation = await chat_service.get_conversation(conversation_id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )
    
    messages = await chat_service.get_conversation_history(conversation_id)
    return {"messages": messages}