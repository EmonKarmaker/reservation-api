from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
import uuid

from app.core.database import get_db
from app.models import Business, Service, BusinessAISettings, AdminUser
from app.api.v1.admin.auth import get_current_admin


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

class BusinessCreate(BaseModel):
    business_name: str
    slug: str
    industry: str = "HOTEL"
    timezone: str = "Asia/Dhaka"


class BusinessUpdate(BaseModel):
    business_name: str | None = None
    timezone: str | None = None
    status: str | None = None


class BusinessResponse(BaseModel):
    id: str
    business_name: str
    slug: str
    industry: str
    industry_label: str | None = None   # ✅ add this
    timezone: str
    status: str | None
    created_at: str | None


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


# ============== Endpoints ==============

@router.get("/", response_model=list[BusinessResponse])
async def list_businesses(
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """List all businesses."""
    
    result = await db.execute(
        select(Business).order_by(Business.created_at.desc())
    )
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
            created_at=b.created_at.isoformat() if b.created_at else None
        )
        for b in businesses
    ]


@router.post("/", response_model=BusinessResponse)
async def create_business(
    request: BusinessCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new business."""
    
    result = await db.execute(
        select(Business).where(Business.slug == request.slug)
    )
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
)

    
    db.add(business)
    await db.flush()
    
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
        industry_label=business.industry_label,  # ✅ add here
        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None
    )


@router.get("/{business_id}", response_model=BusinessResponse)
async def get_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get business details."""
    
    result = await db.execute(
        select(Business).where(Business.id == uuid.UUID(business_id))
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
    return BusinessResponse(
        id=str(business.id),
        business_name=business.business_name,
        slug=business.slug,
        industry=business.industry,
        industry_label=business.industry_label,

        timezone=business.timezone,
        status=business.status,
        created_at=business.created_at.isoformat() if business.created_at else None
    )


@router.patch("/{business_id}", response_model=BusinessResponse)
async def update_business(
    business_id: str,
    request: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update business details."""
    
    result = await db.execute(
        select(Business).where(Business.id == uuid.UUID(business_id))
    )
    business = result.scalar_one_or_none()
    
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    
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
        created_at=business.created_at.isoformat() if business.created_at else None
    )


@router.get("/{business_id}/ai-settings", response_model=AISettingsResponse)
async def get_ai_settings(
    business_id: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get AI settings for a business."""
    
    result = await db.execute(
        select(BusinessAISettings).where(
            BusinessAISettings.business_id == uuid.UUID(business_id)
        )
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
        language=settings.language
    )


@router.patch("/{business_id}/ai-settings", response_model=AISettingsResponse)
async def update_ai_settings(
    business_id: str,
    request: AISettingsUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update AI settings for a business."""
    
    result = await db.execute(
        select(BusinessAISettings).where(
            BusinessAISettings.business_id == uuid.UUID(business_id)
        )
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
        language=settings.language
    )