"""Pydantic schemas for User validation and serialization."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from backend.models.user import UserRole


class UserBase(BaseModel):
    """Base fields for User schemas."""
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., min_length=2, max_length=100, description="User full name")
    phone: Optional[str] = Field(default=None, description="Optional phone number")
    role: UserRole = Field(default=UserRole.CITIZEN, description="User role in system")


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=6, description="User password")


class UserUpdate(BaseModel):
    """Schema for updating user profile."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for public user responses."""
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT Token response schema."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    role: UserRole


class TokenData(BaseModel):
    """Internal token payload schema."""
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[UserRole] = None
