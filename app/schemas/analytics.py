from pydantic import BaseModel
from datetime import datetime


class ResolutionStats(BaseModel):
    """AI resolved vs Human escalation statistics."""
    total_conversations: int
    ai_resolved_count: int
    human_escalated_count: int
    abandoned_count: int
    ai_resolved_percentage: float
    human_escalated_percentage: float
    abandoned_percentage: float


class BookingStats(BaseModel):
    """Booking statistics for dashboard."""
    total_bookings: int
    confirmed_count: int
    pending_count: int
    cancelled_count: int
    total_revenue: float
    currency: str


class DashboardStats(BaseModel):
    """Combined stats for admin dashboard."""
    resolution: ResolutionStats
    bookings: BookingStats
    period_start: datetime
    period_end: datetime