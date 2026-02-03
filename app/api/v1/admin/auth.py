from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer,HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt 
import bcrypt
import uuid 
from app.core.database  import get_db
from app.core.config import settings
from app.models import AdminUser
router=APIRouter()
security=HTTPBearer()
#JWT SECRET (add to your .env file: JWT_SECRETS =your-secret-key)
JWT_SECRET=getattr(settings, 'JWT_SECRET','your-super-secret-key-change-in-production')
JWT_ALGORITHM="HS256"
JWT_EXPIRATION_HOURS=24
#REQUEST/RESPONSE MODEL
class LoginRequest(BaseModel):
    email:str 
    password:str
class LoginResponse(BaseModel):
    access_token:str
    token_type: str="bearer"
    admin_id:str
    email:str
    name:str
    expires_at:str
class AdminResponse(BaseModel):
    id:str
    email:str
    name:str
    role:str
    is_active:bool
    created_at:str | None
class CreateAdminRequest(BaseModel):
    email: str
    password:str
    name:str
    role:str = "ADMIN"
    business_id:str | None = None

#helper function
def hash_password(password: str)-> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
def verify_password(password: str, hashed: str) ->bool:
    """verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

def create_access_token(admin_id:str,email:str)->tuple[str,datetime]:
    """create a jwt access token"""
    expires_at=datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload={
        "sub":admin_id,
        "email":email,
        "exp":expires_at
    }
    token= jwt.encode(payload,JWT_SECRET,algorithm=JWT_ALGORITHM)
    return token,expires_at
async def get_current_admin(
        credentials:HTTPAuthorizationCredentials = Depends(security),
        db: AsyncSession=Depends(get_db)

) -> AdminUser:
    """Dependency to get current authentication admin"""
    try:
        token = credentials.credentials
        payload=jwt.decode(token, JWT_SECRET, algorithms= [JWT_ALGORITHM])
        admin_id=payload.get("sub")
        if not admin_id:
            raise HTTPException(status_code =401, detail="Invalid token")
        result=await db.execute(
            select(AdminUser).where(AdminUser.id == uuid.UUID(admin_id))

        )
        admin =result.scalar_one_or_none()
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        if not admin.is_active:
            raise HTTPException(status_code=401, detail="Admin account is desabled")
        return admin
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")
#endpoints
@router.post("/login",response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db:AsyncSession= Depends(get_db)
):
    """Admin login endpoint"""
    result=await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)

    )
    admin=result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not admin.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    if not verify_password(request.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    #update last login
    admin.last_login_at=datetime.utcnow()
    await db.commit()
    #create token
    token, expires_at=create_access_token(str(admin.id), admin.email)
    return LoginResponse(
        access_token=token,
        admin_id=str(admin.id),
        email=admin.email,
        name=admin.full_name,
        expires_at=expires_at.isoformat()
    )
@router.get("/me",response_model=AdminResponse)
async def get_me(
    current_admin: AdminUser=Depends(get_current_admin)

):
    """get current admin details"""
    return AdminResponse(
        id=str(current_admin.id),
        email=current_admin.email,
        name=current_admin.full_name,
        role=current_admin.role,
        is_active=current_admin.is_active,
        created_at=current_admin.created_at.isoformat() if current_admin.created_at else None


    )
@router.post("/create", response_model=AdminResponse)
async def create_admin(
    request: CreateAdminRequest,
    db: AsyncSession = Depends(get_db),
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Create a new admin (only super admins can do this)."""
    
    # Check if current admin is super admin
    if current_admin.role != "SUPER_ADMIN":
        raise HTTPException(status_code=403, detail="Only super admins can create new admins")
    
    # Check if email already exists
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create admin
    new_admin = AdminUser(
        email=request.email,
        password_hash=hash_password(request.password),
        full_name=request.name,
        role=request.role,
        is_active=True,
        created_at=datetime.utcnow(),
    )
    
    db.add(new_admin)
    await db.commit()
    await db.refresh(new_admin)
    
    return AdminResponse(
        id=str(new_admin.id),
        email=new_admin.email,
        name=new_admin.full_name,
        role=new_admin.role,
        is_active=new_admin.is_active,
        created_at=new_admin.created_at.isoformat() if new_admin.created_at else None
    )
@router.post("/setup-first-admin", response_model=AdminResponse)
async def setup(
    request: CreateAdminRequest,
    db: AsyncSession= Depends(get_db)

):
    """create the first superadmin(only works if no admin exixt).
    this endpoint shouldbe disabled in production adter first use.
    """
    #check if any admin exists
    result=await db.execute(select(AdminUser).limit(1))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Admin already exists. use login instead.")
    #create first admin as super_admin
    admin =AdminUser(
        email=request.email,
        password_hash=hash_password(request.password),
        name=request.name,
        role="SUPER_ADMIN",
        is_active=True,
        created_at=datetime.utcnow()

    )
    db.add(admin)
    await db.commit()
    await db.refresh(admin)
    return AdminResponse(
        id=str(admin.id),
        email=admin.email,
        name=admin.name,
        role=admin.role,
        is_active=admin.is_active,
        created_at=admin.created_at.isoformat() if admin.created_at else None
        )