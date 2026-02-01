from fastapi import APIRouter, Depends,HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime
from decimal import Decimal
import uuid
from app.core.database import get_db
from app.models import Service, AdminUser
from app.api.v1.admin.auth import get_current_admin
router=APIRouter()

#request/response model

class ServiceCreate(BaseModel):
    Service_name: str
    description: str| None=None
    base_price:float
    currency:str = "BDT"
    duration_minutes: int=60
    max_capacity: int=1
    requires_payment:bool=False
class ServiceUpdate(BaseModel):
    service_name: str | None = None
    description: str | None = None
    base_price:float|None=None
    currency:str| None=None
    duration_minutes:int |None = None
    max_capacity: int|None=None
    requires_payment: bool|None=None
    is_active:bool|None=None
class ServiceResponse(BaseModel):
    id:str
    business_id:str
    service_name:str
    description:str|None
    base_price:float
    currency:str
    duration_minutes:int
    max_capacity:int
    requires_payment: bool
    is_active:bool
    created_at :str |None
#endpoints
@router.get("/{business_id}/services", response_model=list[ServiceResponse])
async def list_service(
    business_id: str,
    db:AsyncSession=Depends(get_current_admin)
):
    """list all service for a business"""
    result = await db.execute(
        select(Service)
        .where(Service.business_id == uuid.UUID(business_id))
        .order_by(Service.created_at.desc())
    )
    Service=result.scalars().all()
    return [
        ServiceResponse(
            id=str(s.id),
            business_id=str(s.business_id),
            Service_name=s.service_name,
            description=s.description,
            base_price=float(s.base_price) if s.base_price else 0,
            currency=s.currency or "BDT",
            duration_minutes=s.duration_minutes or 60,
            max_capacity=s.max_capacity or 1,
            requires_payment=s.requres_payment or False,
            is_active=s.is_active,
            created_at=s.created_at.isoformat() if s.created_at else None

        )
        for s in Service
    ]

@router.post("/{business_id}/services", response_model=ServiceResponse)
async def create_service(
    business_id: str,
    request: ServiceCreate,
    db: AsyncSession=Depends(get_db),
    current_admin: AdminUser=Depends(get_current_admin)

):
    """create a noew service for a business"""
    service=Service(
        business_id=uuid.UUID(business_id),
        service_name=request.service_name,
        description=request.description,
        base_price=Decimal(str(request.base_price)),
        currency=request.currency,
        duration_minutes=request.duration_minutes,
        max_capacity=request.max_capacity,
        requires_payment=request.require_payment,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    db.add(service)
    await db.commit()
    await db.refresh(service)
    return ServiceResponse(
        id=str(service.id),
        business_id=str(service.business_id),
        service_name=service.service_name,
        description=service.description,
        base_price=float(service.base_price) if service.base_price else 0,
        currency=service.currency or "BDT",
        duration_minutes=service.duration_minutes or 60,
        max_capacity=service.max_capacity or False,
        requires_payment=service.requires_payment or False,
        is_active=service.is_active,
        created_at=service.created_at.isoformat() if service.created_at else None

    )
@router.get("/{business.id}/service/{service_id}",response_model=ServiceResponse)
async def get_service(
    business_id: str,
    service_id:str,
    db:AsyncSession=Depends(get_db),
    current_admin: AdminUser=Depends(get_current_admin)
):
    """Get service details"""
    result=await db.execute(
        select(Service).where(
        Service.id==uuid.UUID(service_id),
        Service.business_id==uuid.UUID(business_id)
    ))
    service =result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    return ServiceResponse(
        id=str(service.id),
        business_id=(service.business_id),
        service_name=service.service_name,
        description=service.description,
        base_price=float(service_id.base_price) if service.base_price else 0,
        currency=service.currency or "BDT",
        duration_minutes=service.duration_minutes or 60,
        max_capacity=service.max_capacity or 1,
        requires_payment=service.requires_payment or False,
        is_active=service.id_active,
        created_at=service.created_at.isoformat() if service.created_at else None


    )

@router.patch("/{business_id}/services/{service_id}", response_model=ServiceResponse)
async def update_service(
    business_id: str,
    service_id: str,
    request: ServiceUpdate,
    db: AsyncSession=Depends(get_db),
    current_admin:AdminUser=Depends(get_current_admin)
):
    """Update a service"""
    result=await db.execute(
        select(Service).where(
            Service.id==uuid.UUID(service_id),
            Service.business_id==uuid.UUID(business_id)

        )
    )
    service =result.scalar_one_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    if request.service_name is not None:
        service.service_name = request.service_name
    if request.description is not None:
        service.description = request.description
    if request.base_price is not None:
        service.base_price=request.base_price
    if request.currency is not None:
        service.currency= request.currency
    if request.duration_minutes is not None:
        service.duration=request.duration_minutes
    if request.max_capacity is not None:
        service.max_capacity=request.max_capacity
    if  request.requires_payment is not None:
        service.require_payment=request.requires_payment
    if  request.is_active is not None:
        service.is_active = request.is_active
    service.updated_at =datetime.utcnow()
    await db.commit()
    await db.refresh(service)
    
    return ServiceResponse(
        id=str(service.id),
        business_id=str(service.business_id),
        service_name=service.service_name,
        description=service.description,
        base_price=float(service.base_price) if service.base_price else 0,
        currency=service.currency or "BDT",
        duration_minutes=service.duration_minutes or 60,
        max_capacity=service.max_capacity or 1,
        requires_payment=service.requires_payment or False,
        is_active=service.is_active,
        created_at=service.created_at.isoformat() if service.created_at else None
        
    )
@router.delete("/{business_id}/services/{service_id}")
async def delete_service(
    business_id: str,
    service_id: str,
    db:AsyncSession=Depends(get_db),
    current_admin:AdminUser=Depends(get_current_admin)
):
    """Delete (deactivate) a service"""
    result=await db.execute(
        select(Service).where(
            Service.id==uuid.UUID(service_id),
            Service.business_id==uuid.UUID(business_id)
        )
    )
    service=result.scalar_on_or_none()
    if not service:
        raise HTTPException(status_code=404, detail="Service not found")
    service.is_active=False
    service.updated_at=datetime.utcnow()
    await db.commit()
    return {"message": "Service deactivated"}