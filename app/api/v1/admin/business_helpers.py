from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional, Tuple

from fastapi import HTTPException
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.business import Business
from app.models.business_profile import BusinessProfile
from app.models.business_address import BusinessAddress
from app.models.other_models import BusinessOperatingHours

from .business_schemas import (
    ALLOWED_INDUSTRIES,
    BusinessProfileIn,
    BusinessAddressIn,
    OperatingHoursBulk,
)


def map_industry(value: str | None) -> tuple[str, str | None]:
    """
    Returns:
      - enum_value: always one of ALLOWED_INDUSTRIES
      - label_value: original normalized input
    """
    if not value:
        return "OTHER", None

    label = value.strip().upper()
    if label in ALLOWED_INDUSTRIES:
        return label, label
    return "OTHER", label


async def get_business_or_404(db: AsyncSession, business_id: str) -> Business:
    try:
        bid = uuid.UUID(business_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid business_id")

    result = await db.execute(select(Business).where(Business.id == bid))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def upsert_profile(
    db: AsyncSession,
    business_id: uuid.UUID,
    payload: BusinessProfileIn,
) -> BusinessProfile:
    result = await db.execute(
        select(BusinessProfile).where(BusinessProfile.business_id == business_id)
    )
    profile = result.scalar_one_or_none()

    if not profile:
        profile = BusinessProfile(business_id=business_id)

    profile.contact_person = payload.contact_person
    profile.email = str(payload.email) if payload.email else None
    profile.phone = payload.phone

    db.add(profile)
    await db.flush()
    return profile


async def upsert_address(
    db: AsyncSession,
    business_id: uuid.UUID,
    payload: BusinessAddressIn,
) -> BusinessAddress:
    result = await db.execute(
        select(BusinessAddress).where(
            BusinessAddress.business_id == business_id,
            BusinessAddress.address_type == payload.address_type,
        )
    )
    addr = result.scalar_one_or_none()

    if not addr:
        addr = BusinessAddress(
            id=uuid.uuid4(),
            business_id=business_id,
            address_type=payload.address_type,
        )

    addr.street = payload.street
    addr.city = payload.city
    addr.state = payload.state
    addr.zip_code = payload.zip_code
    addr.country = payload.country

    db.add(addr)
    await db.flush()
    return addr


async def replace_operating_hours(
    db: AsyncSession,
    business_id: uuid.UUID,
    payload: OperatingHoursBulk,
) -> None:
    # Replace weekly schedule for admin (simple and safe)
    await db.execute(
        delete(BusinessOperatingHours).where(
            BusinessOperatingHours.business_id == business_id
        )
    )

    for rule in payload.weekly_hours:
        # Validate rule logic
        if rule.is_closed:
            open_time = None
            close_time = None
        else:
            open_time = rule.open_time
            close_time = rule.close_time
            if open_time is None or close_time is None:
                raise HTTPException(
                    status_code=400,
                    detail=f"day_of_week={rule.day_of_week}: open_time/close_time required when is_closed=false",
                )

        row = BusinessOperatingHours(
            id=uuid.uuid4(),
            business_id=business_id,
            day_of_week=rule.day_of_week,
            open_time=open_time,
            close_time=close_time,
            is_closed=rule.is_closed,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(row)

    await db.flush()
