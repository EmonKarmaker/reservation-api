import enum


class BookingStatus(str, enum.Enum):
    INITIATED = "INITIATED"
    SLOT_SELECTED = "SLOT_SELECTED"
    CONTACT_COLLECTED = "CONTACT_COLLECTED"
    PAYMENT_PENDING = "PAYMENT_PENDING"
    PENDING_PAYMENT = "PENDING_PAYMENT"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"
    CANCELED = "CANCELED"
    FAILED = "FAILED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    RESCHEDULED = "RESCHEDULED"
    EXPIRED = "EXPIRED"


class ResolutionType(str, enum.Enum):
    AI_RESOLVED = "AI_RESOLVED"
    HUMAN_HANDOFF = "HUMAN_HANDOFF"
    HUMAN_ESCALATED = "HUMAN_ESCALATED"
    USER_ABANDONED = "USER_ABANDONED"
    FAILED = "FAILED"
    CALL_REQUESTED = "CALL_REQUESTED"


class ConversationStatus(str, enum.Enum):
    STARTED = "STARTED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"
    ABANDONED = "ABANDONED"


class ConversationChannel(str, enum.Enum):
    CHAT = "CHAT"
    VOICE = "VOICE"
    HUMAN = "HUMAN"


class ConversationOutcome(str, enum.Enum):
    BOOKED = "BOOKED"
    ESCALATED = "ESCALATED"
    DROPPED = "DROPPED"


class HandoffStatus(str, enum.Enum):
    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class PaymentStatus(str, enum.Enum):
    CREATED = "CREATED"
    PENDING = "PENDING"
    PAID = "PAID"
    FAILED = "FAILED"
    EXPIRED = "EXPIRED"
    REFUNDED = "REFUNDED"


class PaymentProvider(str, enum.Enum):
    STRIPE = "STRIPE"
    SSLCOMMERZ = "SSLCOMMERZ"
    RAZORPAY = "RAZORPAY"
    OTHER = "OTHER"


class Industry(str, enum.Enum):
    HOTEL = "HOTEL"
    RESTAURANT = "RESTAURANT"
    SALON = "SALON"
    CLINIC = "CLINIC"
    OTHER = "OTHER"


class AvailabilityExceptionType(str, enum.Enum):
    CLOSED = "CLOSED"
    SPECIAL_OPEN = "SPECIAL_OPEN"