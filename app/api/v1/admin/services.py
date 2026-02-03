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
    # New fields
    category: str | None = "GENERAL"
    location: str | None = None
    is_popular: bool = False
    service_type: str = "IN_PERSON"
    max_capacity: int = 1
    icon: str | None = None


class ServiceUpdate(BaseModel):
    service_name: str | None = None
    description: str | None = None
    base_price: float | None = None
    currency: str | None = None
    duration_minutes: int | None = None
    is_active: bool | None = None
    # New fields
    category: str | None = None
    location: str | None = None
    is_popular: bool | None = None
    service_type: str | None = None
    max_capacity: int | None = None
    icon: str | None = None


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
    # New fields
    category: str | None
    location: str | None
    is_popular: bool
    service_type: str
    max_capacity: int | None
    icon: str | None
    created_at: str | None


# ============== Helper Function ==============

def service_to_response(service: Service) -> ServiceResponse:
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
        category=service.category,
        location=service.location,
        is_popular=service.is_popular or False,
        service_type=service.service_type or "IN_PERSON",
        max_capacity=service.max_capacity,
        icon=service.icon,
        created_at=service.created_at.isoformat() if service.created_at else None
    )


# ============== Endpoints ==============

@router.get("/businesses/{bid}/services", response_model=list[ServiceResponse])
async def list_services(
    bid: str,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """List all services for a business."""
    result = await db.execute(
        select(Service)
        .where(Service.business_id == uuid.UUID(bid))
        .order_by(Service.is_popular.desc(), Service.created_at.desc())
    )
    services = result.scalars().all()
    return [service_to_response(s) for s in services]


@router.post("/businesses/{bid}/services", response_model=ServiceResponse)
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
        category=request.category,
        location=request.location,
        is_popular=request.is_popular,
        service_type=request.service_type,
        max_capacity=request.max_capacity,
        icon=request.icon,
        created_at=datetime.utcnow(),
    )

    db.add(service)
    await db.commit()
    await db.refresh(service)

    return service_to_response(service)


@router.get("/businesses/{bid}/services/{sid}", response_model=ServiceResponse)
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

    return service_to_response(service)


@router.patch("/businesses/{bid}/services/{sid}", response_model=ServiceResponse)
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

    # Update basic fields
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
    
    # Update new fields
    if request.category is not None:
        service.category = request.category
    if request.location is not None:
        service.location = request.location
    if request.is_popular is not None:
        service.is_popular = request.is_popular
    if request.service_type is not None:
        service.service_type = request.service_type
    if request.max_capacity is not None:
        service.max_capacity = request.max_capacity
    if request.icon is not None:
        service.icon = request.icon

    service.updated_at = datetime.utcnow()
    await db.commit()
    await db.refresh(service)

    return service_to_response(service)


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
