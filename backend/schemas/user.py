"""Pydantic v2 schemas for User registration, login, updates, password management, and responses."""

from datetime import datetime
import re
from typing import List, Optional, Any
from uuid import UUID
from pydantic import (
    BaseModel,
    EmailStr,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
)
from backend.models.user import UserRole


# ------------------------------------------------------------------------------
# Helper Validation Functions
# ------------------------------------------------------------------------------
def _validate_name_string(v: Optional[str]) -> Optional[str]:
    """Strip whitespace, check length, and ensure no HTML/script tags in name."""
    if v is None:
        return v
    v = v.strip()
    if len(v) < 2 or len(v) > 100:
        raise ValueError("Name must be between 2 and 100 characters long")
    if "<" in v or ">" in v or "script" in v.lower():
        raise ValueError("Name contains illegal HTML or script characters")
    return v


def _validate_password_complexity(v: str) -> str:
    """Validate password complexity: min 8 chars, 1 upper, 1 lower, 1 digit, 1 special char."""
    if len(v) < 8:
        raise ValueError("Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", v):
        raise ValueError("Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", v):
        raise ValueError("Password must contain at least one lowercase letter")
    if not re.search(r"\d", v):
        raise ValueError("Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]", v):
        raise ValueError("Password must contain at least one special character")
    return v


def _validate_phone_number(v: Optional[str]) -> Optional[str]:
    """Validate international phone number format if provided."""
    if v is None or v.strip() == "":
        return None
    v = v.strip()
    pattern = r"^\+?[1-9]\d{6,14}$"
    if not re.match(pattern, v):
        raise ValueError("Phone number must be a valid international format (e.g. +1234567890)")
    return v


def _validate_http_url(v: Optional[str]) -> Optional[str]:
    """Validate URL starts with http:// or https:// if provided."""
    if v is None or v.strip() == "":
        return None
    v = v.strip()
    if not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("Avatar URL must start with http:// or https://")
    return v


# ------------------------------------------------------------------------------
# Input Schemas
# ------------------------------------------------------------------------------
class UserRegister(BaseModel):
    """Schema for user registration request."""
    name: str = Field(..., description="User full name (2-100 chars, no HTML)", json_schema_extra={"example": "Jane Doe"})
    email: EmailStr = Field(..., description="User email address (automatically lowercased)", json_schema_extra={"example": "jane.doe@example.com"})
    password: str = Field(..., description="Strong password meeting complexity rules", json_schema_extra={"example": "SecureP@ss123"})
    phone: Optional[str] = Field(default=None, description="Optional international phone number", json_schema_extra={"example": "+14155552671"})
    role: Optional[UserRole] = Field(default=UserRole.CITIZEN, description="Role within system (defaults to citizen)")
    location_city: Optional[str] = Field(default=None, description="Optional city location", json_schema_extra={"example": "Metropolis"})

    @field_validator("name", mode="before")
    @classmethod
    def check_name(cls, v: Any, info) -> str:
        if not v and hasattr(info, "data") and info.data.get("full_name"):
            v = info.data.get("full_name")
        res = _validate_name_string(v)
        if res is None:
            raise ValueError("Name is required")
        return res

    @model_validator(mode="before")
    @classmethod
    def map_full_name(cls, data: Any) -> Any:
        if isinstance(data, dict):
            if "full_name" in data and "name" not in data:
                data["name"] = data["full_name"]
        return data

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone_number(v)


class UserLogin(BaseModel):
    """Schema for user login credentials."""
    email: EmailStr = Field(..., description="Registered email address", json_schema_extra={"example": "jane.doe@example.com"})
    password: str = Field(..., description="User password", json_schema_extra={"example": "SecureP@ss123"})
    remember_me: bool = Field(default=False, description="Flag to request extended token lifetime")

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserUpdate(BaseModel):
    """Schema for updating current user profile attributes."""
    name: Optional[str] = Field(default=None, description="Updated full name (2-100 chars)")
    phone: Optional[str] = Field(default=None, description="Updated contact phone number")
    bio: Optional[str] = Field(default=None, max_length=500, description="Updated user short bio")
    avatar_url: Optional[str] = Field(default=None, description="Updated profile image URL")
    location_lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Updated latitude (-90 to 90)")
    location_lng: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Updated longitude (-180 to 180)")
    location_city: Optional[str] = Field(default=None, description="Updated city")
    location_area: Optional[str] = Field(default=None, description="Updated area or neighborhood")
    location_address: Optional[str] = Field(default=None, description="Updated street address")

    @field_validator("name")
    @classmethod
    def check_name(cls, v: Optional[str]) -> Optional[str]:
        return _validate_name_string(v)

    @field_validator("phone")
    @classmethod
    def check_phone(cls, v: Optional[str]) -> Optional[str]:
        return _validate_phone_number(v)

    @field_validator("avatar_url")
    @classmethod
    def check_avatar(cls, v: Optional[str]) -> Optional[str]:
        return _validate_http_url(v)

    @field_validator("bio")
    @classmethod
    def check_bio(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            v = v.strip()
            if "<" in v or ">" in v or "script" in v.lower():
                raise ValueError("Bio contains illegal HTML or script characters")
        return v


class UserChangePassword(BaseModel):
    """Schema for changing account password."""
    current_password: str = Field(..., description="Existing account password")
    new_password: str = Field(..., description="New replacement password")
    confirm_password: str = Field(..., description="Confirmation of new replacement password")

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @model_validator(mode="after")
    def validate_passwords_match_and_differ(self) -> "UserChangePassword":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm password do not match")
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from current password")
        return self


class UserForgotPassword(BaseModel):
    """Schema for requesting password reset link."""
    email: EmailStr = Field(..., description="Registered user email", json_schema_extra={"example": "jane.doe@example.com"})

    @field_validator("email", mode="before")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().lower()
        return v


class UserResetPassword(BaseModel):
    """Schema for resetting password using reset token."""
    token: str = Field(..., description="Valid 32-character reset token")
    new_password: str = Field(..., description="New replacement password")
    confirm_password: str = Field(..., description="Confirmation of new replacement password")

    @field_validator("new_password")
    @classmethod
    def check_new_password(cls, v: str) -> str:
        return _validate_password_complexity(v)

    @model_validator(mode="after")
    def validate_passwords_match(self) -> "UserResetPassword":
        if self.new_password != self.confirm_password:
            raise ValueError("New password and confirm password do not match")
        return self


class UserRoleUpdate(BaseModel):
    """Schema for administrative role assignment updates."""
    role: UserRole = Field(..., description="Target platform role")


# ------------------------------------------------------------------------------
# Output Schemas
# ------------------------------------------------------------------------------
class UserResponse(BaseModel):
    """Standard user response schema (excludes raw ID and sensitive fields)."""
    uuid: UUID = Field(..., description="Public UUID identifier")
    name: str = Field(..., description="User full name")
    email: str = Field(..., description="User email address")
    phone: Optional[str] = Field(default=None, description="Contact phone number")
    avatar_url: Optional[str] = Field(default=None, description="Profile avatar URL")
    bio: Optional[str] = Field(default=None, description="User bio")
    role: UserRole = Field(..., description="Platform role")
    is_active: bool = Field(..., description="Account active status")
    is_verified: bool = Field(..., description="Email verification status")
    location_city: Optional[str] = Field(default=None, description="User city")
    location_area: Optional[str] = Field(default=None, description="User area")
    total_issues_reported: int = Field(default=0, description="Issues count reported by user")
    total_issues_resolved: int = Field(default=0, description="Issues count resolved by user")
    reputation_score: float = Field(default=0.0, description="Calculated reputation score")
    created_at: datetime = Field(..., description="Account registration date")
    last_login: Optional[datetime] = Field(default=None, description="Last login timestamp")

    model_config = ConfigDict(from_attributes=True)


class UserPublicResponse(BaseModel):
    """Minimal public user response schema for lists and public views."""
    uuid: UUID = Field(..., description="Public UUID identifier")
    name: str = Field(..., description="User full name")
    avatar_url: Optional[str] = Field(default=None, description="Profile avatar URL")
    role: UserRole = Field(..., description="Platform role")
    reputation_score: float = Field(default=0.0, description="Reputation score")
    total_issues_reported: int = Field(default=0, description="Issues count reported")

    model_config = ConfigDict(from_attributes=True)


class UserProfileResponse(UserResponse):
    """Detailed user profile response schema including engagement metrics and coordinates."""
    total_votes_given: int = Field(default=0, description="Total upvotes cast")
    total_comments: int = Field(default=0, description="Total comments posted")
    location_lat: Optional[float] = Field(default=None, description="Latitude coordinate")
    location_lng: Optional[float] = Field(default=None, description="Longitude coordinate")

    model_config = ConfigDict(from_attributes=True)


class TokenResponse(BaseModel):
    """JWT token response schema including tokens and embedded User object."""
    access_token: str = Field(..., description="Encoded JWT access token")
    refresh_token: str = Field(..., description="Encoded JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    expires_in: int = Field(..., description="Access token expiration time in seconds")
    user: UserResponse = Field(..., description="Authenticated user profile details")


class UserListResponse(BaseModel):
    """Paginated user list response schema."""
    users: List[UserPublicResponse] = Field(..., description="List of user profiles")
    total: int = Field(..., description="Total matching users count")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Page size limit")
    total_pages: int = Field(..., description="Total available pages")


class TokenData(BaseModel):
    """Internal JWT payload data structure."""
    sub: Optional[str] = None
    uuid: Optional[str] = None
    role: Optional[UserRole] = None
    type: Optional[str] = None


# Backwards Compatibility Aliases
UserCreate = UserRegister
UserPasswordChange = UserChangePassword
Token = TokenResponse


class UserBase(BaseModel):
    """Base user schema for backwards compatibility."""
    email: EmailStr = Field(..., description="User email address")
    name: str = Field(..., description="User full name")
    phone: Optional[str] = Field(default=None, description="Optional phone number")
    role: UserRole = Field(default=UserRole.CITIZEN, description="User role in system")
    avatar_url: Optional[str] = Field(default=None, description="URL of user profile picture")
