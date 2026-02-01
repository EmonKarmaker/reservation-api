from pydantic import BaseModel, Field, EmailStr
from datetime import datetime
from uuid import UUID


# ============== Login Schemas ==============

class LoginRequest(BaseModel):
    """Admin login credentials."""
    email: EmailStr
    password: str = Field(..., min_length=6)


class TokenResponse(BaseModel):
    """JWT token returned after successful login."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ============== Admin User Schemas ==============

class AdminUserBase(BaseModel):
    email: EmailStr
    full_name: str | None = Field(None, max_length=120)
    role: str = Field(..., max_length=40)


class AdminUserCreate(AdminUserBase):
    """Create new admin user."""
    password: str = Field(..., min_length=6)


class AdminUserResponse(AdminUserBase):
    """Admin user info returned from API."""
    id: UUID
    is_active: bool
    last_login_at: datetime | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserUpdate(BaseModel):
    """Update admin user - all fields optional."""
    full_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class PasswordChange(BaseModel):
    """Change password request."""
    current_password: str = Field(..., min_length=6)
    new_password: str = Field(..., min_length=6)