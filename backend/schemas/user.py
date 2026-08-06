"""Pydantic v2 schemas for User validation, serialization, authentication, and responses."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from backend.models.user import UserRole


class UserBase(BaseModel):
    """Base schema for shared user attributes."""
    email: EmailStr = Field(..., description="User email address")
    full_name: str = Field(..., min_length=2, max_length=100, description="User full name")
    phone: Optional[str] = Field(default=None, description="Optional phone number")
    role: UserRole = Field(default=UserRole.CITIZEN, description="User role in system")
    avatar_url: Optional[str] = Field(default=None, description="URL of user profile picture")


class UserCreate(UserBase):
    """Schema for user registration."""
    password: str = Field(..., min_length=6, max_length=100, description="User raw password")


class UserLogin(BaseModel):
    """Schema for user login authentication."""
    email: EmailStr = Field(..., description="User registered email")
    password: str = Field(..., description="User password")


class UserUpdate(BaseModel):
    """Schema for updating user profile attributes."""
    full_name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    is_verified: Optional[bool] = None


class UserResponse(UserBase):
    """Schema for public user profile response."""
    id: int
    uuid: str
    is_active: bool
    is_verified: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    """JWT Token response schema."""
    access_token: str
    token_type: str = "bearer"
    user_id: int
    user_uuid: Optional[str] = None
    role: UserRole


class TokenData(BaseModel):
    """Internal token payload schema."""
    email: Optional[str] = None
    user_id: Optional[int] = None
    role: Optional[UserRole] = None
