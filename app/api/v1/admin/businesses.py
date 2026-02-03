from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime, time
from typing import Optional, Literal, List
import uuid

from app.core.database import get_db

from app.models.business import Business
from app.models.other_models import BusinessAISettings, AdminUser, BusinessOperatingHours
from app.models.business_profile import BusinessProfile
from app.models.business_address import BusinessAddress

# IMPORTANT: your project already uses this dependency
# make sure this import exists in your codebase:
from app.api.v1.admin.auth import get_current_admin  # <-- adjust path if different


router = APIRouter()

ALLOWED_INDUSTRIES = {"HOTEL", "RESTAURANT", "SALON", "CLINIC", "OTHER", "SPA"}


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


# ============== Request/Response Models ==============

class OperatingHoursRule(BaseModel):
    # Keep consistent with your DB model (commonly: 0=Sun..6=Sat OR 1=Mon..7=Sun).
    # Your DB unique index exists on (business_id, day_of_week) – so just stay consistent everywhere.
    day_of_week: int = Field(ge=0, le=6)
    open_time: time
    close_time: time


class OperatingHoursBulk(BaseModel):
    timezone: Optional[str] = None
    weekly_hours: List[OperatingHoursRule]


class BusinessProfileIn(BaseModel):
    contact_person: Optional[str] = Field(default=None, max_length=120)
    email: Optional[EmailStr] = None
    phone: Optional[str] = Field(default=None, max_length=40)


class BusinessAddressIn(BaseModel):
    address_type: Literal["PRIMARY", "BILLING", "BRANCH"] = "PRIMARY"
    street: Optional[str] = None
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    zip_code: Optional[str] = Field(default=None, max_length=30)
    country: Optional[str] = Field(default=None, max_length=100)
class BusinessFormCreate(BaseModel):
    # Business Information (screenshot)
    business_name: str
    business_type: str = Field(default="HOTEL")  # dropdown in UI
    timezone: str = Field(default="Asia/Dhaka")

    # Contact Details (screenshot)
    contact_person: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None

    # Address (screenshot)
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip_code: Optional[str] = None
    country: Optional[str] = None

    # Business Hours (screenshot - simple version)
    opening_time: Optional[time] = None
    closing_time: Optional[time] = None
    is_closed: bool = False


class BusinessCreate(BaseModel):
    # Core identity (stable)
    business_name: str
    slug: str
    industry: str = "HOTEL"
    timezone: str = "Asia/Dhaka"

    # Optional onboarding payload (from your UI form)
    profile: Optional[BusinessProfileIn] = None
    address: Optional[BusinessAddressIn] = None
    hours: Optional[OperatingHoursBulk] = None


class BusinessUpdate(BaseModel):
    business_name: str | None = None
    timezone: str | None = None
    status: str | None = None


class BusinessResponse(BaseModel):
    id: str
    business_name: str
    slug: str
    industry: str
    industry_label: str | None = None
    timezone: str
    status: str | None
    created_at: str | None


class BusinessProfileResponse(BaseModel):
    business_id: str
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None


class BusinessAddressResponse(BaseModel):
    id: str
    business_id: str
    address_type: str
    street: str | None = None
    city: str | None = None
    state: str | None = None
    zip_code: str | None = None
    country: str | None = None


class OperatingHoursResponse(BaseModel):
    business_id: str
    weekly_hours: list[OperatingHoursRule]


class AISettingsUpdate(BaseModel):
    agent_name: str | None = None
    tone_of_voice: str | None = None
    welcome_message: str | None = None
    fallback_message: str | None = None
    escalation_message: str | None = None
    max_retries: int | None = None
    language: str | None = None


class AISettingsResponse(BaseModel):
    id: str
    business_id: str
    agent_name: str
    tone_of_voice: str | None
    welcome_message: str | None
    fallback_message: str | None
    escalation_message: str | None
    max_retries: int | None
    language: str | None


# ============== Internal helpers ==============

async def _get_business_or_404(db: AsyncSession, business_id: str) -> Business:
    try:
        bid = uuid.UUID(business_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid business_id")

    result = await db.execute(select(Business).where(Business.id == bid))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return business


async def _upsert_profile(db: AsyncSession, business_id: uuid.UUID, payload: BusinessProfileIn) -> BusinessProfile:
    result = await db.execute(select(BusinessProfile).where(BusinessProfile.business_id == business_id))
    profile = result.scalar_one_or_none()

    if not profile:
        profile = BusinessProfile(business_id=business_id)

    profile.contact_person = payload.contact_person
    profile.email = str(payload.email) if payload.email else None
    profile.phone = payload.phone

    db.add(profile)
    await db.flush()
    return profile


async def _upsert_address(db: AsyncSession, business_id: uuid.UUID, payload: BusinessAddressIn) -> BusinessAddress:
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


async def _replace_operating_hours(db: AsyncSession, business_id: uuid.UUID, payload: OperatingHoursBulk):
    # Simple enterprise-safe behavior for admin: replace weekly schedule
    await db.execute(delete(BusinessOperatingHours).where(BusinessOperatingHours.business_id == business_id))

    for rule in payload.weekly_hours:
        row = BusinessOperatingHours(
            id=uuid.uuid4(),
            business_id=business_id,
            day_of_week=rule.day_of_week,
            open_time=rule.open_time,
            close_time=rule.close_time,
        )
        db.add(row)

    await db.flush()


# ============== Endpoints ==============

@router.get("/", response_model=list[BusinessResponse])
async def list_businesses(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(select(Business).order_by(Business.created_at.desc()))
    businesses = result.scalars().all()

    return [
        BusinessResponse(
            id=str(b.id),
            business_name=b.business_name,
            slug=b.slug,
            industry=b.industry,
            industry_label=b.industry_label,
            timezone=b.timezone,
            status=b.status,
            created_at=b.created_at.isoformat() if b.created_at else None,
        )
        for b in businesses
    ]


@router.post("/", response_model=BusinessResponse)
async def create_business(
    request: BusinessCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    # slug unique check
    result = await db.execute(select(Business).where(Business.slug == request.slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    enum_industry, industry_label = map_industry(request.industry)

    business = Business(
        business_name=request.business_name,
        slug=request.slug,
        industry=enum_industry,
        industry_label=industry_label,
        timezone=request.timezone,
        status="ACTIVE",
        created_by_admin_id=current_admin.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    db.add(business)
    await db.flush()

    # Create default AI settings (existing behavior)
    ai_settings = BusinessAISettings(
        business_id=business.id,
        agent_name="Assistant",
        tone_of_voice="friendly and professional",
        welcome_message="Hello! How can I help you today?",
        fallback_message="I'm sorry, I didn't understand that.",
        escalation_message="I'll connect you with a human representative.",
        max_retries=3,
        language="en",
    )
    db.add(ai_settings)

    # OPTIONAL: onboarding payload (profile/address/hours)
    if request.profile:
        await _upsert_profile(db, business.id, request.profile)

    if request.address:
        await _upsert_address(db, business.id, request.address)

    if request.hours:
        # if request.hours.timezone provided, you can also update business.timezone (optional)
        if request.hours.timezone:
            business.timezone = request.hours.timezone
        await _replace_operating_hours(db, business.id, request.hours)

    await db.commit()
    await db.refresh(business)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )

@router.post("/form", response_model=BusinessResponse)
async def create_business_from_form(
    request: BusinessFormCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    # 1) slug from name (simple)
    slug = request.business_name.strip().lower().replace(" ", "-")

    # 2) slug unique check
    result = await db.execute(select(Business).where(Business.slug == slug))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Business slug already exists")

    # 3) map business_type -> industry enum
    enum_industry, industry_label = map_industry(request.business_type)

    # 4) create Business row
    business = Business(
        business_name=request.business_name,
        slug=slug,
        industry=enum_industry,
        industry_label=industry_label,
        timezone=request.timezone,
        status="ACTIVE",
        created_by_admin_id=current_admin.id,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(business)
    await db.flush()

    # 5) upsert profile
    await _upsert_profile(
        db,
        business.id,
        BusinessProfileIn(
            contact_person=request.contact_person,
            email=request.email,
            phone=request.phone,
        ),
    )

    # 6) upsert PRIMARY address
    await _upsert_address(
        db,
        business.id,
        BusinessAddressIn(
            address_type="PRIMARY",
            street=request.street_address,
            city=request.city,
            state=request.state,
            zip_code=request.zip_code,
            country=request.country,
        ),
    )

    # 7) apply simple hours to all 7 days (only if times provided)
    if request.opening_time and request.closing_time:
        weekly = []
        for day in range(0, 7):
            weekly.append(
                OperatingHoursRule(
                    day_of_week=day,
                    open_time=request.opening_time,
                    close_time=request.closing_time,
                    is_closed=request.is_closed,
                )
            )
        await _replace_operating_hours(
            db,
            business.id,
            OperatingHoursBulk(timezone=request.timezone, weekly_hours=weekly),
        )

    # 8) create AI settings (same behavior as your normal create)
    ai_settings = BusinessAISettings(
        business_id=business.id,
        agent_name="Assistant",
        tone_of_voice="friendly and professional",
        welcome_message="Hello! How can I help you today?",
        fallback_message="I'm sorry, I didn't understand that.",
        escalation_message="I'll connect you with a human representative.",
        max_retries=3,
        language="en",
    )
    db.add(ai_settings)

    await db.commit()
    await db.refresh(business)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )

@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: str,
    request: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    if request.business_name is not None:
        business.business_name = request.business_name
    if request.timezone is not None:
        business.timezone = request.timezone
    if request.status is not None:
        business.status = request.status

    business.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(business)

    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None,
    )


# ------- NEW: Business Profile -------

@router.put("/{business_id}/profile", response_model=BusinessProfileResponse)
async def upsert_business_profile(
    business_id: str,
    request: BusinessProfileIn,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)
    profile = await _upsert_profile(db, business.id, request)
    await db.commit()
    await db.refresh(profile)

    return BusinessProfileResponse(
        business_id=str(profile.business_id),
        contact_person=profile.contact_person,
        email=profile.email,
        phone=profile.phone,
    )


@router.get("/{business_id}/profile", response_model=BusinessProfileResponse)
async def get_business_profile(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    result = await db.execute(select(BusinessProfile).where(BusinessProfile.business_id == business.id))
    profile = result.scalar_one_or_none()
    if not profile:
        return BusinessProfileResponse(business_id=str(business.id))

    return BusinessProfileResponse(
        business_id=str(profile.business_id),
        contact_person=profile.contact_person,
        email=profile.email,
        phone=profile.phone,
    )


# ------- NEW: Business Addresses -------

@router.put("/{business_id}/addresses", response_model=BusinessAddressResponse)
async def upsert_business_address(
    business_id: str,
    request: BusinessAddressIn,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)
    addr = await _upsert_address(db, business.id, request)
    await db.commit()
    await db.refresh(addr)

    return BusinessAddressResponse(
        id=str(addr.id),
        business_id=str(addr.business_id),
        address_type=addr.address_type,
        street=addr.street,
        city=addr.city,
        state=addr.state,
        zip_code=addr.zip_code,
        country=addr.country,
    )


@router.get("/{business_id}/addresses", response_model=list[BusinessAddressResponse])
async def list_business_addresses(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    result = await db.execute(select(BusinessAddress).where(BusinessAddress.business_id == business.id))
    addresses = result.scalars().all()

    return [
        BusinessAddressResponse(
            id=str(a.id),
            business_id=str(a.business_id),
            address_type=a.address_type,
            street=a.street,
            city=a.city,
            state=a.state,
            zip_code=a.zip_code,
            country=a.country,
        )
        for a in addresses
    ]


# ------- NEW: Operating Hours -------

@router.put("/{business_id}/operating-hours", response_model=dict)
async def replace_operating_hours(
    business_id: str,
    request: OperatingHoursBulk,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    if request.timezone:
        business.timezone = request.timezone

    await _replace_operating_hours(db, business.id, request)
    await db.commit()

    return {"ok": True, "business_id": str(business.id), "count": len(request.weekly_hours)}


@router.get("/{business_id}/operating-hours", response_model=OperatingHoursResponse)
async def get_operating_hours(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    business = await _get_business_or_404(db, business_id)

    result = await db.execute(
        select(BusinessOperatingHours).where(BusinessOperatingHours.business_id == business.id).order_by(BusinessOperatingHours.day_of_week.asc())
    )
    rows = result.scalars().all()

    weekly = [
        OperatingHoursRule(day_of_week=r.day_of_week, open_time=r.open_time, close_time=r.close_time)
        for r in rows
    ]
    return OperatingHoursResponse(business_id=str(business.id), weekly_hours=weekly)


# ------- Existing AI settings endpoints (unchanged) -------

@router.get("/{business_id}/ai-settings", response_model=AISettingsResponse)
async def get_ai_settings(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(BusinessAISettings).where(BusinessAISettings.business_id == uuid.UUID(business_id))
    )
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail="AI settings not found")

    return AISettingsResponse(
        id=str(settings.id),
        business_id=str(settings.business_id),
        agent_name=settings.agent_name,
        tone_of_voice=settings.tone_of_voice,
        welcome_message=settings.welcome_message,
        fallback_message=settings.fallback_message,
        escalation_message=settings.escalation_message,
        max_retries=settings.max_retries,
        language=settings.language,
    )


@router.patch("/{business_id}/ai-settings", response_model=AISettingsResponse)
async def update_ai_settings(
    business_id: str,
    request: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin),
):
    result = await db.execute(
        select(BusinessAISettings).where(BusinessAISettings.business_id == uuid.UUID(business_id))
    )
    settings = result.scalar_one_or_none()

    if not settings:
        raise HTTPException(status_code=404, detail="AI settings not found")

    if request.agent_name is not None:
        settings.agent_name = request.agent_name
    if request.tone_of_voice is not None:
        settings.tone_of_voice = request.tone_of_voice
    if request.welcome_message is not None:
        settings.welcome_message = request.welcome_message
    if request.fallback_message is not None:
        settings.fallback_message = request.fallback_message
    if request.escalation_message is not None:
        settings.escalation_message = request.escalation_message
    if request.max_retries is not None:
        settings.max_retries = request.max_retries
    if request.language is not None:
        settings.language = request.language

    settings.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(settings)

    return AISettingsResponse(
        id=str(settings.id),
        business_id=str(settings.business_id),
        agent_name=settings.agent_name,
        tone_of_voice=settings.tone_of_voice,
        welcome_message=settings.welcome_message,
        fallback_message=settings.fallback_message,
        escalation_message=settings.escalation_message,
        max_retries=settings.max_retries,
        language=settings.language,
    )
