from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
import uuid

from app.core.database import get_db
from app.models import Service, AdminUser
from app.api.v1.admin.auth import get_current_admin


router = APIRouter()


# ============== Request/Response Models ==============

class ServiceCreate(BaseModel):
    service_name: str
    slug: str
    description: str | None = None
    base_price: float | None = None
    currency: str = "BDT"
    duration_minutes: int = 60


class ServiceUpdate(BaseModel):
    service_name: str | None = None
    description: str | None = None
    base_price: float | None = None
    currency: str | None = None
    duration_minutes: int | None = None
    is_active: bool | None = None


class ServiceResponse(BaseModel):
    id: str
    business_id: str
    slug: str
    service_name: str
    description: str | None
    base_price: float | None
    currency: str | None
    duration_minutes: int | None
    is_active: bool
    created_at: str | None


# ============== Endpoints ==============

@router.get("/businesses/{bid}/services")
async def list_services(
    bid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """List all services for a business."""
    
    result = await db.execute(
        select(Service)
        .where(Service.business_id == uuid.UUID(bid))
        .order_by(Service.created_at.desc())
    )
    services = result.scalars().all()
    
    return [
        ServiceResponse(
            id=str(s.id),
            business_id=str(s.business_id),
            slug=s.slug,
            service_name=s.service_name,
            description=s.description,
            base_price=float(s.base_price) if s.base_price else None,
            currency=s.currency,
            duration_minutes=s.duration_minutes,
            is_active=s.is_active,
            created_at=s.created_at.isoformat() if s.created_at else None
        )
        for s in services
    ]


@router.post("/businesses/{bid}/services")
async def create_service(
    bid: str,
    request: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new service for a business."""
    
    service = Service(
        business_id=uuid.UUID(bid),
        slug=request.slug,
        service_name=request.service_name,
        description=request.description,
        base_price=Decimal(str(request.base_price)) if request.base_price else None,
        currency=request.currency,
        duration_minutes=request.duration_minutes,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    
    db.add(service)
    await db.commit()
    await db.refresh(service)
    
    return ServiceResponse(
        id=str(service.id),
        business_id=str(service.business_id),
        slug=service.slug,
        service_name=service.service_name,
        description=service.description,
        base_price=float(service.base_price) if service.base_price else None,
        currency=service.currency,
        duration_minutes=service.duration_minutes,
        is_active=service.is_active,
        created_at=service.created_at.isoformat() if service.created_at else None
    )


@router.get("/businesses/{bid}/services/{sid}")
async def get_service(
    bid: str,
    sid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get service details."""
    
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(sid),
            Service.business_id == uuid.UUID(bid)
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    return ServiceResponse(
        id=str(service.id),
        business_id=str(service.business_id),
        slug=service.slug,
        service_name=service.service_name,
        description=service.description,
        base_price=float(service.base_price) if service.base_price else None,
        currency=service.currency,
        duration_minutes=service.duration_minutes,
        is_active=service.is_active,
        created_at=service.created_at.isoformat() if service.created_at else None
    )


@router.patch("/businesses/{bid}/services/{sid}")
async def update_service(
    bid: str,
    sid: str,
    request: ServiceUpdate,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Update a service."""
    
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(sid),
            Service.business_id == uuid.UUID(bid)
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    if request.service_name is not None:
        service.service_name = request.service_name
    if request.description is not None:
        service.description = request.description
    if request.base_price is not None:
        service.base_price = Decimal(str(request.base_price))
    if request.currency is not None:
        service.currency = request.currency
    if request.duration_minutes is not None:
        service.duration_minutes = request.duration_minutes
    if request.is_active is not None:
        service.is_active = request.is_active
    
    service.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(service)
    
    return ServiceResponse(
        id=str(service.id),
        business_id=str(service.business_id),
        slug=service.slug,
        service_name=service.service_name,
        description=service.description,
        base_price=float(service.base_price) if service.base_price else None,
        currency=service.currency,
        duration_minutes=service.duration_minutes,
        is_active=service.is_active,
        created_at=service.created_at.isoformat() if service.created_at else None
    )


@router.delete("/businesses/{bid}/services/{sid}")
async def delete_service(
    bid: str,
    sid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Delete (deactivate) a service."""
    
    result = await db.execute(
        select(Service).where(
            Service.id == uuid.UUID(sid),
            Service.business_id == uuid.UUID(bid)
        )
    )
    service = result.scalar_one_or_none()
    
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    
    service.is_active = False
    service.updated_at = datetime.utcnow()
    await db.commit()
    
    return {"message": "Service deactivated successfully"}