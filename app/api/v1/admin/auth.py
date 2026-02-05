from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
import jwt
import bcrypt
import uuid
import secrets

from app.core.database import get_db
from app.core.config import settings
from app.models import AdminUser

router = APIRouter()
security = HTTPBearer()

# JWT Settings from config
JWT_SECRET = settings.JWT_SECRET
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = settings.JWT_EXPIRATION_HOURS

# Hardcoded Admin from config
ADMIN_EMAIL = settings.ADMIN_EMAIL
ADMIN_NAME = settings.ADMIN_NAME
ADMIN_DEFAULT_PASSWORD = settings.ADMIN_DEFAULT_PASSWORD


# ============== Request/Response Models ==============

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    admin_id: str
    email: str
    name: str
    expires_at: str


class AdminResponse(BaseModel):
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: str | None


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str
    confirm_password: str


class MessageResponse(BaseModel):
    message: str
    success: bool = True


# ============== Helper Functions ==============

def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))


def create_access_token(admin_id: str, email: str) -> tuple[str, datetime]:
    """Create a JWT access token"""
    expires_at = datetime.utcnow() + timedelta(hours=JWT_EXPIRATION_HOURS)
    payload = {
        "sub": admin_id,
        "email": email,
        "exp": expires_at
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    return token, expires_at


def create_reset_token() -> str:
    """Create a secure random reset token"""
    return secrets.token_urlsafe(32)


async def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: AsyncSession = Depends(get_db)
) -> AdminUser:
    """Dependency to get current authenticated admin"""
    try:
        token = credentials.credentials
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        admin_id = payload.get("sub")
        
        if not admin_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        result = await db.execute(
            select(AdminUser).where(AdminUser.id == uuid.UUID(admin_id))
        )
        admin = result.scalar_one_or_none()
        
        if not admin:
            raise HTTPException(status_code=401, detail="Admin not found")
        if not admin.is_active:
            raise HTTPException(status_code=401, detail="Admin account is disabled")
        
        return admin

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def ensure_admin_exists(db: AsyncSession) -> AdminUser:
    """
    Ensure the hardcoded admin exists in the database.
    Creates the admin if it doesn't exist.
    """
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == ADMIN_EMAIL)
    )
    admin = result.scalar_one_or_none()
    
    if not admin:
        # Create the hardcoded admin
        admin = AdminUser(
            email=ADMIN_EMAIL,
            password_hash=hash_password(ADMIN_DEFAULT_PASSWORD),
            full_name=ADMIN_NAME,
            role="ADMIN",
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.add(admin)
        await db.commit()
        await db.refresh(admin)
    
    return admin


# ============== Endpoints ==============

@router.post("/login", response_model=LoginResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Admin login endpoint.
    Only the hardcoded admin email can login.
    Auto-creates admin on first login if not exists.
    """
    # Check if email matches hardcoded admin
    if request.email != ADMIN_EMAIL:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Ensure admin exists (auto-create on first login)
    await ensure_admin_exists(db)
    
    # Get admin from database
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)
    )
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    if not admin.is_active:
        raise HTTPException(status_code=401, detail="Account is disabled")
    
    if not verify_password(request.password, admin.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    # Update last login
    admin.last_login_at = datetime.utcnow()
    await db.commit()
    
    # Create token
    token, expires_at = create_access_token(str(admin.id), admin.email)
    
    return LoginResponse(
        access_token=token,
        admin_id=str(admin.id),
        email=admin.email,
        name=admin.full_name or ADMIN_NAME,
        expires_at=expires_at.isoformat()
    )


@router.get("/me", response_model=AdminResponse)
async def get_me(
    current_admin: AdminUser = Depends(get_current_admin)
):
    """Get current admin details"""
    return AdminResponse(
        id=str(current_admin.id),
        email=current_admin.email,
        name=current_admin.full_name or "",
        role=current_admin.role,
        is_active=current_admin.is_active,
        created_at=current_admin.created_at.isoformat() if current_admin.created_at else None
    )


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: ChangePasswordRequest,
    current_admin: AdminUser = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """
    Change password for the logged-in admin.
    Requires current password for verification.
    """
    # Verify current password
    if not verify_password(request.current_password, current_admin.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    
    # Validate new password
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="New passwords do not match")
    
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    if request.new_password == request.current_password:
        raise HTTPException(status_code=400, detail="New password must be different from current password")
    
    # Update password
    current_admin.password_hash = hash_password(request.new_password)
    current_admin.updated_at = datetime.utcnow()
    await db.commit()
    
    return MessageResponse(message="Password changed successfully")


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Request password reset.
    Only works for the hardcoded admin email.
    In production, this would send an email with reset link.
    """
    # Only allow for hardcoded admin email
    if request.email != ADMIN_EMAIL:
        # Don't reveal if email exists or not (security)
        return MessageResponse(message="If this email exists, a reset link will be sent")
    
    # Get admin
    result = await db.execute(
        select(AdminUser).where(AdminUser.email == request.email)
    )
    admin = result.scalar_one_or_none()
    
    if not admin:
        return MessageResponse(message="If this email exists, a reset link will be sent")
    
    # Generate reset token (valid for 1 hour)
    reset_token = create_reset_token()
    reset_expires = datetime.utcnow() + timedelta(hours=1)
    
    # Store token in JWT format for stateless validation
    reset_payload = {
        "sub": str(admin.id),
        "email": admin.email,
        "type": "password_reset",
        "exp": reset_expires
    }
    reset_jwt = jwt.encode(reset_payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # In production, send email with reset link
    # For now, return the token (REMOVE IN PRODUCTION)
    print(f"Password reset token for {admin.email}: {reset_jwt}")
    
    return MessageResponse(
        message=f"Password reset token generated. Token: {reset_jwt}"
    )


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Reset password using the reset token.
    """
    # Validate passwords match
    if request.new_password != request.confirm_password:
        raise HTTPException(status_code=400, detail="Passwords do not match")
    
    if len(request.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    
    # Verify reset token
    try:
        payload = jwt.decode(request.token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        if payload.get("type") != "password_reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
        
        admin_id = payload.get("sub")
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=400, detail="Reset token has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    
    # Get admin
    result = await db.execute(
        select(AdminUser).where(AdminUser.id == uuid.UUID(admin_id))
    )
    admin = result.scalar_one_or_none()
    
    if not admin:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    
    # Update password
    admin.password_hash = hash_password(request.new_password)
    admin.updated_at = datetime.utcnow()
    await db.commit()
    
    return MessageResponse(message="Password reset successfully. You can now login with your new password.")


@router.post("/init", response_model=MessageResponse)
async def init_admin(
    db: AsyncSession = Depends(get_db)
):
    """
    Initialize the hardcoded admin account.
    Call this once to create the admin in the database.
    Safe to call multiple times - won't duplicate.
    """
    admin = await ensure_admin_exists(db)
    
    return MessageResponse(
        message=f"Admin initialized: {admin.email}"
    )
