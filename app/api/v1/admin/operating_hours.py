from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, time
import uuid

from app.core.database import get_db
from app.models import BusinessOperatingHours, AdminUser
from app.api.v1.admin.auth import get_current_admin


router = APIRouter()


# ============== Request/Response Models ==============

class OperatingHoursItem(BaseModel):
    day_of_week: int  # 0=Monday, 6=Sunday
    day_name: str
    open_time: str | None  # "09:00"
    close_time: str | None  # "18:00"
    is_closed: bool


class OperatingHoursUpdate(BaseModel):
    day_of_week: int
    open_time: str | None = None  # "09:00"
    close_time: str | None = None  # "18:00"
    is_closed: bool = False


class BulkOperatingHoursUpdate(BaseModel):
    hours: list[OperatingHoursUpdate]


# ============== Helper ==============

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def time_to_str(t: time | None) -> str | None:
    if t is None:
        return None
    return t.strftime("%H:%M")


def str_to_time(s: str | None) -> time | None:
    if s is None:
        return None
    try:
        return datetime.strptime(s, "%H:%M").time()
    except ValueError:
        return None


# ============== Endpoints ==============

@router.get("/businesses/{bid}/operating-hours", response_model=list[OperatingHoursItem])
async def get_operating_hours(
    bid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get operating hours for a business (all 7 days)."""
    
    result = await db.execute(
        select(BusinessOperatingHours)
        .where(BusinessOperatingHours.business_id == uuid.UUID(bid))
        .order_by(BusinessOperatingHours.day_of_week)
    )
    hours = result.scalars().all()
    
    # Create a dict for quick lookup
    hours_dict = {h.day_of_week: h for h in hours}
    
    # Return all 7 days (create default if missing)
    response = []
    for day in range(7):
        if day in hours_dict:
            h = hours_dict[day]
            response.append(OperatingHoursItem(
                day_of_week=day,
                day_name=DAY_NAMES[day],
                open_time=time_to_str(h.open_time),
                close_time=time_to_str(h.close_time),
                is_closed=h.is_closed or False
            ))
        else:
            # Default: 9 AM - 6 PM, open
            response.append(OperatingHoursItem(
                day_of_week=day,
                day_name=DAY_NAMES[day],
                open_time="09:00",
                close_time="18:00",
                is_closed=False
            ))
    
    return response


@router.put("/businesses/{bid}/operating-hours", response_model=list[OperatingHoursItem])
async def update_operating_hours(
    bid: str,
    request: BulkOperatingHoursUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update operating hours for a business (bulk update all days)."""
    
    business_id = uuid.UUID(bid)
    
    for item in request.hours:
        # Check if record exists
        result = await db.execute(
            select(BusinessOperatingHours).where(
                BusinessOperatingHours.business_id == business_id,
                BusinessOperatingHours.day_of_week == item.day_of_week
            )
        )
        existing = result.scalar_one_or_none()
        
        if existing:
            # Update
            existing.open_time = str_to_time(item.open_time)
            existing.close_time = str_to_time(item.close_time)
            existing.is_closed = item.is_closed
            existing.updated_at = datetime.utcnow()
        else:
            # Create
            new_hours = BusinessOperatingHours(
                business_id=business_id,
                day_of_week=item.day_of_week,
                open_time=str_to_time(item.open_time),
                close_time=str_to_time(item.close_time),
                is_closed=item.is_closed,
                created_at=datetime.utcnow()
            )
            db.add(new_hours)
    
    await db.commit()
    
    # Return updated hours
    return await get_operating_hours(bid, db, current_admin)


@router.patch("/businesses/{bid}/operating-hours/{day}", response_model=OperatingHoursItem)
async def update_single_day_hours(
    bid: str,
    day: int,
    request: OperatingHoursUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update operating hours for a single day."""
    
    if day < 0 or day > 6:
        raise HTTPException(status_code=400, detail="Day must be 0-6 (Monday-Sunday)")
    
    business_id = uuid.UUID(bid)
    
    result = await db.execute(
        select(BusinessOperatingHours).where(
            BusinessOperatingHours.business_id == business_id,
            BusinessOperatingHours.day_of_week == day
        )
    )
    existing = result.scalar_one_or_none()
    
    if existing:
        if request.open_time is not None:
            existing.open_time = str_to_time(request.open_time)
        if request.close_time is not None:
            existing.close_time = str_to_time(request.close_time)
        existing.is_closed = request.is_closed
        existing.updated_at = datetime.utcnow()
    else:
        existing = BusinessOperatingHours(
            business_id=business_id,
            day_of_week=day,
            open_time=str_to_time(request.open_time) or datetime.strptime("09:00", "%H:%M").time(),
            close_time=str_to_time(request.close_time) or datetime.strptime("18:00", "%H:%M").time(),
            is_closed=request.is_closed,
            created_at=datetime.utcnow()
        )
        db.add(existing)
    
    await db.commit()
    await db.refresh(existing)
    
    return OperatingHoursItem(
        day_of_week=existing.day_of_week,
        day_name=DAY_NAMES[existing.day_of_week],
        open_time=time_to_str(existing.open_time),
        close_time=time_to_str(existing.close_time),
        is_closed=existing.is_closed or False
    )
