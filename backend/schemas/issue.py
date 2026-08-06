"""Pydantic schemas for Issue, Vote, and Comment validation."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict
from backend.models.issue import IssueCategory, IssueStatus, IssuePriority
from backend.schemas.user import UserResponse


class CommentBase(BaseModel):
    """Base schema for issue comments."""
    content: str = Field(..., min_length=1, description="Comment text content")


class CommentCreate(CommentBase):
    """Schema for creating a comment."""
    pass


class CommentResponse(CommentBase):
    """Schema for returning a comment."""
    id: int
    issue_id: int
    user_id: int
    created_at: datetime
    user: UserResponse

    model_config = ConfigDict(from_attributes=True)


class IssueBase(BaseModel):
    """Base fields for community issues."""
    title: str = Field(..., min_length=5, max_length=200, description="Brief summary of the issue")
    description: str = Field(..., min_length=10, description="Detailed explanation of the issue")
    category: IssueCategory = Field(default=IssueCategory.OTHER, description="Issue category")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="GPS latitude")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="GPS longitude")
    address: Optional[str] = Field(default=None, description="Human-readable address or landmark")
    image_url: Optional[str] = Field(default=None, description="URL of uploaded issue photo")


class IssueCreate(IssueBase):
    """Schema for submitting a new issue."""
    priority: Optional[IssuePriority] = Field(default=IssuePriority.MEDIUM)


class IssueUpdate(BaseModel):
    """Schema for updating an existing issue."""
    title: Optional[str] = Field(default=None, min_length=5, max_length=200)
    description: Optional[str] = Field(default=None, min_length=10)
    category: Optional[IssueCategory] = None
    status: Optional[IssueStatus] = None
    priority: Optional[IssuePriority] = None
    latitude: Optional[float] = Field(default=None, ge=-90.0, le=90.0)
    longitude: Optional[float] = Field(default=None, ge=-180.0, le=180.0)
    address: Optional[str] = None
    image_url: Optional[str] = None
    assigned_to_id: Optional[int] = None


class IssueResponse(IssueBase):
    """Detailed response schema for an issue."""
    id: int
    status: IssueStatus
    priority: IssuePriority
    reporter_id: int
    assigned_to_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    reporter: UserResponse
    assigned_to: Optional[UserResponse] = None
    vote_count: int = 0
    comment_count: int = 0

    model_config = ConfigDict(from_attributes=True)


class VoteResponse(BaseModel):
    """Response schema for vote actions."""
    id: int
    issue_id: int
    user_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
