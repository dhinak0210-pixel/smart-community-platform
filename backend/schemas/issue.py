"""Pydantic v2 schemas for Issue, Comment, Vote, and IssueHistory validation and API responses."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from uuid import UUID
from pydantic import (
    BaseModel,
    Field,
    ConfigDict,
    field_validator,
    model_validator,
)

from backend.models.issue import (
    IssueCategory,
    IssueStatus,
    IssuePriority,
    CommentType,
    VoteType,
    ChangeType,
)
from backend.schemas.user import UserPublicResponse


# ------------------------------------------------------------------------------
# Input Schemas
# ------------------------------------------------------------------------------
class IssueCreate(BaseModel):
    """Schema for submitting a new community issue report."""
    title: str = Field(..., min_length=5, max_length=200, description="Brief summary title of the issue")
    description: str = Field(..., min_length=20, max_length=5000, description="Detailed explanation of the issue (min 20 characters)")
    category: Optional[IssueCategory] = Field(default=IssueCategory.OTHER, description="Category of issue (AI will auto-suggest if unspecified)")
    priority: Optional[IssuePriority] = Field(default=IssuePriority.MEDIUM, description="Initial priority level")
    location_lat: float = Field(..., ge=-90.0, le=90.0, description="GPS latitude coordinate (-90 to 90)")
    location_lng: float = Field(..., ge=-180.0, le=180.0, description="GPS longitude coordinate (-180 to 180)")
    location_address: Optional[str] = Field(default=None, max_length=500, description="Human-readable street address")
    location_city: Optional[str] = Field(default=None, max_length=100, description="City name")
    location_area: Optional[str] = Field(default=None, max_length=100, description="Neighborhood or area name")
    location_landmark: Optional[str] = Field(default=None, max_length=200, description="Nearby prominent landmark")
    image_url: Optional[str] = Field(default=None, max_length=500, description="Optional uploaded image URL")
    temp_id: Optional[str] = Field(default=None, max_length=200, description="Optional temporary image ID for cloud storage promotion")

    @field_validator("title")
    @classmethod
    def sanitize_title(cls, v: str) -> str:
        clean_v = v.strip()
        if "<" in clean_v or ">" in clean_v:
            raise ValueError("Title cannot contain HTML or script tags")
        return clean_v

    @field_validator("description")
    @classmethod
    def sanitize_description(cls, v: str) -> str:
        clean_v = v.strip()
        if "<script" in clean_v.lower():
            raise ValueError("Description cannot contain script tags")
        return clean_v


class IssueUpdate(BaseModel):
    """Schema for updating core issue details by reporter or admin."""
    title: Optional[str] = Field(default=None, min_length=5, max_length=200, description="Updated issue title")
    description: Optional[str] = Field(default=None, min_length=20, max_length=5000, description="Updated issue description")
    category: Optional[IssueCategory] = Field(default=None, description="Updated issue category")
    location_address: Optional[str] = Field(default=None, max_length=500, description="Updated address")
    location_landmark: Optional[str] = Field(default=None, max_length=200, description="Updated landmark")

    @field_validator("title", "description")
    @classmethod
    def sanitize_optional_text(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            clean_v = v.strip()
            if "<script" in clean_v.lower():
                raise ValueError("Text content cannot contain script tags")
            return clean_v
        return v


class IssueStatusUpdate(BaseModel):
    """Schema for authority status transition and department assignment."""
    status: IssueStatus = Field(..., description="Target resolution status")
    status_note: Optional[str] = Field(default=None, max_length=500, description="Authority explanation for status change")
    rejection_reason: Optional[str] = Field(default=None, max_length=500, description="Reason required if status is set to rejected")
    assigned_to: Optional[int] = Field(default=None, description="Integer ID of assigned user/staff")
    assigned_department: Optional[str] = Field(default=None, max_length=100, description="Assigned municipal department name")

    @model_validator(mode="after")
    def validate_rejection_reason(self) -> "IssueStatusUpdate":
        if self.status == IssueStatus.REJECTED or str(self.status) == "rejected":
            if not self.rejection_reason or not self.rejection_reason.strip():
                raise ValueError("Rejection reason is required when status is set to 'rejected'")
        return self


class IssuePriorityUpdate(BaseModel):
    """Schema for overriding issue priority."""
    priority: IssuePriority = Field(..., description="Target priority level")
    reason: Optional[str] = Field(default=None, max_length=500, description="Explanation for priority override")


class IssueResolutionUpdate(BaseModel):
    """Schema for marking issue resolved with official summary note."""
    resolution_note: str = Field(..., min_length=20, max_length=1000, description="Detailed explanation of resolution actions taken")
    resolved_by_department: Optional[str] = Field(default=None, max_length=100, description="Department responsible for fix")


class CitizenResolutionConfirm(BaseModel):
    """Schema for citizen feedback and star rating on completed resolution."""
    confirmed: bool = Field(..., description="True if citizen confirms fix is satisfactory")
    rating: int = Field(..., ge=1, le=5, description="Star rating from 1 (poor) to 5 (excellent)")
    feedback: Optional[str] = Field(default=None, max_length=500, description="Optional written feedback")


class CommentCreate(BaseModel):
    """Schema for posting a discussion comment."""
    content: str = Field(..., min_length=2, max_length=1000, description="Comment text body")
    comment_type: Optional[CommentType] = Field(default=CommentType.CITIZEN_COMMENT, description="Classification type of comment")
    parent_id: Optional[int] = Field(default=None, description="Parent comment ID for threaded replies")

    @field_validator("content")
    @classmethod
    def sanitize_comment(cls, v: str) -> str:
        clean_v = v.strip()
        if "<script" in clean_v.lower():
            raise ValueError("Comments cannot contain script tags")
        return clean_v


class CommentUpdate(BaseModel):
    """Schema for editing comment body."""
    content: str = Field(..., min_length=2, max_length=1000, description="Updated comment text body")

    @field_validator("content")
    @classmethod
    def sanitize_comment(cls, v: str) -> str:
        clean_v = v.strip()
        if "<script" in clean_v.lower():
            raise ValueError("Comments cannot contain script tags")
        return clean_v


class VoteCreate(BaseModel):
    """Schema for casting a vote on an issue."""
    vote_type: Optional[VoteType] = Field(default=VoteType.UPVOTE, description="Type of vote cast")


# ------------------------------------------------------------------------------
# Output Schemas
# ------------------------------------------------------------------------------
class IssueMapMarker(BaseModel):
    """Compact payload for map marker rendering."""
    uuid: UUID = Field(..., description="Issue public UUID")
    title: str = Field(..., description="Issue title")
    status: IssueStatus = Field(..., description="Issue status")
    priority: IssuePriority = Field(..., description="Issue priority")
    category: IssueCategory = Field(..., description="Issue category")
    location_lat: float = Field(..., description="Latitude")
    location_lng: float = Field(..., description="Longitude")
    vote_count: int = Field(..., description="Upvote tally")
    created_at: datetime = Field(..., description="Creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class CommentResponse(BaseModel):
    """Response schema for discussion comments."""
    uuid: UUID = Field(..., description="Comment public UUID")
    content: str = Field(..., description="Comment content body")
    comment_type: CommentType = Field(..., description="Comment classification")
    is_pinned: bool = Field(..., description="Pinned status")
    is_edited: bool = Field(..., description="Edited status")
    like_count: int = Field(..., description="Total likes count")
    user: Optional[UserPublicResponse] = Field(default=None, description="Author profile")
    replies: Optional[List["CommentResponse"]] = Field(default_factory=list, description="Threaded replies")
    created_at: datetime = Field(..., description="Created timestamp")
    edited_at: Optional[datetime] = Field(default=None, description="Edited timestamp")

    model_config = ConfigDict(from_attributes=True)


class VoteResponse(BaseModel):
    """Response schema for cast votes."""
    issue_uuid: UUID = Field(..., description="Public UUID of voted issue")
    vote_type: VoteType = Field(..., description="Type of vote")
    user: UserPublicResponse = Field(..., description="Voter public profile")
    created_at: datetime = Field(..., description="Vote timestamp")

    model_config = ConfigDict(from_attributes=True)


class IssueHistoryResponse(BaseModel):
    """Audit log entry for issue updates."""
    uuid: UUID = Field(..., description="History entry public UUID")
    change_type: ChangeType = Field(..., description="Type of modification")
    old_value: Optional[str] = Field(default=None, description="Previous attribute value")
    new_value: Optional[str] = Field(default=None, description="Updated attribute value")
    note: Optional[str] = Field(default=None, description="Audit note explanation")
    changed_by: Optional[UserPublicResponse] = Field(default=None, description="User who triggered change")
    created_at: datetime = Field(..., description="Change timestamp")

    model_config = ConfigDict(from_attributes=True)


class IssueSummary(BaseModel):
    """Summary representation for issue list endpoints."""
    id: int = Field(..., description="Issue primary key integer ID")
    uuid: UUID = Field(..., description="Issue public UUID")
    title: str = Field(..., description="Title")
    short_description: Optional[str] = Field(default=None, description="Preview text snippet")
    category: IssueCategory = Field(..., description="Category")
    status: IssueStatus = Field(..., description="Status")
    priority: IssuePriority = Field(..., description="Priority")
    location_address: Optional[str] = Field(default=None, description="Street address")
    location_city: Optional[str] = Field(default=None, description="City")
    image_url: Optional[str] = Field(default=None, description="Primary photo URL")
    vote_count: int = Field(default=0, description="Upvotes count")
    comment_count: int = Field(default=0, description="Comments count")
    view_count: int = Field(default=0, description="Page views count")
    days_open: int = Field(default=0, description="Days open count")
    reported_by: Optional[UserPublicResponse] = Field(default=None, description="Reporter profile")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last modification timestamp")

    model_config = ConfigDict(from_attributes=True)


class IssueDetail(IssueSummary):
    """Full detail view for single issue endpoint."""
    description: str = Field(..., description="Complete detailed description")
    location_lat: float = Field(..., description="Latitude")
    location_lng: float = Field(..., description="Longitude")
    location_area: Optional[str] = Field(default=None, description="Neighborhood area")
    location_landmark: Optional[str] = Field(default=None, description="Nearby landmark")
    image_urls: Optional[List[str]] = Field(default_factory=list, description="All uploaded photo URLs")
    ai_suggested_category: Optional[str] = Field(default=None, description="AI recommended category")
    ai_category_confidence: Optional[float] = Field(default=None, description="AI confidence rating")
    ai_tags: Optional[List[str]] = Field(default_factory=list, description="Auto-generated tags")
    ai_image_analysis: Optional[Dict[str, Any]] = Field(default=None, description="Vision model detection payload")
    assigned_to: Optional[UserPublicResponse] = Field(default=None, description="Assigned staff/volunteer profile")
    assigned_department: Optional[str] = Field(default=None, description="Assigned department name")
    status_note: Optional[str] = Field(default=None, description="Authority status update note")
    resolution_note: Optional[str] = Field(default=None, description="Resolution summary note")
    resolved_at: Optional[datetime] = Field(default=None, description="Resolution timestamp")
    history: List[IssueHistoryResponse] = Field(default_factory=list, description="Change history audit log")
    comments: List[CommentResponse] = Field(default_factory=list, description="Discussion comments")

    model_config = ConfigDict(from_attributes=True)


class IssueListResponse(BaseModel):
    """Paginated list response for community issue queries."""
    issues: List[IssueSummary] = Field(..., description="List of issue summaries for current page")
    total: int = Field(..., description="Total count matching query")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total available pages")
    filters_applied: Dict[str, Any] = Field(default_factory=dict, description="Active search and filter parameters")


class IssueStatsResponse(BaseModel):
    """Aggregate statistics for analytical reporting and dashboard counters."""
    total_issues: int = Field(..., description="Total issues in platform")
    by_status: Dict[str, int] = Field(..., description="Counts grouped by status")
    by_category: Dict[str, int] = Field(..., description="Counts grouped by category")
    by_priority: Dict[str, int] = Field(..., description="Counts grouped by priority")
    resolved_this_week: int = Field(..., description="Issues resolved in last 7 days")
    reported_this_week: int = Field(..., description="Issues reported in last 7 days")
    average_resolution_days: float = Field(..., description="Average days taken to resolve issues")
    top_areas: List[Dict[str, Any]] = Field(..., description="Areas with highest issue volume")
    resolution_rate: float = Field(..., description="Resolution rate percentage (0.0 to 100.0)")


# Backwards Compatibility Aliases
IssueResponse = IssueDetail

