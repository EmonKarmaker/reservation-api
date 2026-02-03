# app/models/__init__.py

# Base lives here in your project:
from app.core.database import Base
# add this with the other imports
from app.models.other_models import HandoffRequest

# Core models
from app.models.business import Business
from app.models.service import Service
from app.models.booking import Booking
from app.models.conversation import Conversation
from app.models.conversation_message import ConversationMessage
from app.models.call_session import CallSession

# Extra tables + exceptions/rules used by services
from app.models.other_models import (
    AdminUser,
    BusinessAISettings,
    BusinessOperatingHours,
    BusinessAvailabilityException,
    ServiceCapacityRule,
)

__all__ = [
    "HandoffRequest",

    "Base",
    "Business",
    "Service",
    "Booking",
    "Conversation",
    "ConversationMessage",
    "CallSession",
    "AdminUser",
    "BusinessAISettings",
    "BusinessOperatingHours",
    "BusinessAvailabilityException",
    "ServiceCapacityRule",
]
