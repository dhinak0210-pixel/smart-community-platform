"""Issue, Comment, Vote, and IssueHistory ORM database models for Smart Community Platform."""

from __future__ import annotations
from datetime import datetime
import enum
import uuid as uuid_pkg
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    String, Integer, Text, Float, Boolean, DateTime, Enum as SQLEnum, ForeignKey, Index, UniqueConstraint, CheckConstraint, JSON
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.user import User


class GUID(TypeDecorator):
    """Platform-independent GUID type.
    Uses PostgreSQL native UUID type, otherwise uses CHAR(36) storing stringified UUIDs on SQLite.
    """
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=True))
        else:
            return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid_pkg.UUID):
            return str(uuid_pkg.UUID(str(value)))
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        if not isinstance(value, uuid_pkg.UUID):
            return uuid_pkg.UUID(str(value))
        return value


class IssueCategory(str, enum.Enum):
    """Categories for community issues."""
    INFRASTRUCTURE = "infrastructure"
    WASTE = "waste"
    SAFETY = "safety"
    ENVIRONMENT = "environment"
    UTILITIES = "utilities"
    TRAFFIC = "traffic"
    NOISE = "noise"
    FLOODING = "flooding"
    OTHER = "other"


class IssueStatus(str, enum.Enum):
    """Lifecycle statuses for reported community issues."""
    REPORTED = "reported"
    UNDER_REVIEW = "under_review"
    ACKNOWLEDGED = "acknowledged"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    PENDING_CITIZEN = "pending_citizen"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    DUPLICATE = "duplicate"


class IssuePriority(str, enum.Enum):
    """Priority levels for issue urgency."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CommentType(str, enum.Enum):
    """Classification types for issue discussion comments."""
    CITIZEN_COMMENT = "citizen_comment"
    AUTHORITY_UPDATE = "authority_update"
    SYSTEM_MESSAGE = "system_message"
    RESOLUTION_NOTE = "resolution_note"


class VoteType(str, enum.Enum):
    """Voting options for community engagement."""
    UPVOTE = "upvote"
    IMPORTANT = "important"


class ChangeType(str, enum.Enum):
    """Audit log types for tracking issue updates."""
    STATUS_CHANGE = "status_change"
    PRIORITY_CHANGE = "priority_change"
    ASSIGNMENT_CHANGE = "assignment_change"
    CATEGORY_CHANGE = "category_change"
    AI_UPDATE = "ai_update"
    COMMENT_ADDED = "comment_added"
    IMAGE_ADDED = "image_added"
    DETAILS_EDIT = "details_edit"


class Issue(Base):
    """Community Issue ORM model representing reported civic problems."""

    __tablename__ = "issues"

    # Core Fields
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True, comment="Primary key integer ID")
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(GUID(), default=uuid_pkg.uuid4, unique=True, index=True, nullable=False, comment="Public unique UUID for API responses")
    title: Mapped[str] = mapped_column(String(200), nullable=False, comment="Brief title describing the issue")
    description: Mapped[str] = mapped_column(Text, nullable=False, comment="Detailed description of the issue")
    short_description: Mapped[Optional[str]] = mapped_column(String(300), nullable=True, comment="Auto-generated short preview snippet")

    # Category Fields
    category: Mapped[IssueCategory] = mapped_column(SQLEnum(IssueCategory, name="issue_category"), default=IssueCategory.OTHER, nullable=False, index=True, comment="Primary issue category")
    ai_suggested_category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="AI recommended category classification")
    ai_category_confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="AI category confidence score (0.0 to 1.0)")

    # Status Fields
    status: Mapped[IssueStatus] = mapped_column(SQLEnum(IssueStatus, name="issue_status"), default=IssueStatus.REPORTED, nullable=False, index=True, comment="Current issue status")
    status_note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Authority note appended during status updates")
    rejection_reason: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Explanation if issue status is set to rejected")
    duplicate_of_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("issues.id", ondelete="SET NULL"), nullable=True, comment="Pointer to original issue if marked as duplicate")

    # Priority Fields
    priority: Mapped[IssuePriority] = mapped_column(SQLEnum(IssuePriority, name="issue_priority"), default=IssuePriority.MEDIUM, nullable=False, index=True, comment="Priority level")
    ai_suggested_priority: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="AI recommended priority rating")
    manual_priority_override: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Flag set True when priority is manually overridden by a human")

    # Location Fields
    location_lat: Mapped[float] = mapped_column(Float, nullable=False, comment="Latitude coordinate (-90 to 90)")
    location_lng: Mapped[float] = mapped_column(Float, nullable=False, comment="Longitude coordinate (-180 to 180)")
    location_address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Human-readable street address")
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="City name")
    location_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Neighborhood or district area")
    location_landmark: Mapped[Optional[str]] = mapped_column(String(200), nullable=True, comment="Prominent nearby landmark")

    # Media Fields
    image_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Primary upload photo URL")
    image_urls: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list, nullable=True, comment="List of additional upload photo URLs")
    video_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Optional video upload URL")
    ai_image_analysis: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True, comment="Object detection and analysis payload from vision model")

    # Assignment Fields
    reporter_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="Foreign key of reporting user")
    assigned_to_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True, comment="Foreign key of assigned staff or volunteer")
    assigned_department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Responsible municipal department name")
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Timestamp of department/user assignment")

    # Engagement Fields
    vote_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, index=True, comment="Cached tally of upvotes")
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Cached tally of discussion comments")
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Count of issue page views")
    share_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Count of social shares")
    follower_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Count of users following issue updates")

    # AI Fields
    ai_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True, comment="Flag indicating whether AI agents have processed issue")
    ai_processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Timestamp when AI analysis completed")
    ai_tags: Mapped[Optional[List[str]]] = mapped_column(JSON, default=list, nullable=True, comment="List of auto-generated search tags")
    similarity_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Vector similarity score against duplicate candidates")

    # Resolution Fields
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Timestamp when marked resolved")
    resolved_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, comment="Foreign key of user who marked issue resolved")
    resolution_note: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True, comment="Summary of resolution actions taken")
    citizen_confirmed_resolved: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True, comment="Flag set by reporter confirming fix")
    resolution_rating: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="Citizen rating score from 1 to 5 stars")
    resolution_feedback: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Citizen written feedback on resolution quality")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="Issue creation timestamp")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Last modification timestamp")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Soft delete timestamp")

    # Relationships
    reported_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[reporter_id],
        back_populates="issues_reported",
        lazy="select",
    )
    assigned_to: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_to_id],
        back_populates="issues_assigned",
        lazy="select",
    )
    resolved_by: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by_id],
        lazy="select",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="select",
    )
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="select",
    )
    history: Mapped[List["IssueHistory"]] = relationship(
        "IssueHistory",
        back_populates="issue",
        cascade="all, delete-orphan",
        lazy="select",
    )
    duplicate_issue: Mapped[Optional["Issue"]] = relationship(
        "Issue",
        remote_side=[id],
        foreign_keys=[duplicate_of_id],
        lazy="select",
    )

    # Indexes and Table Arguments
    __table_args__ = (
        Index("ix_issues_geo_composite", "location_lat", "location_lng"),
        Index("ix_issues_status_category_composite", "status", "category"),
        CheckConstraint("location_lat >= -90.0 AND location_lat <= 90.0", name="chk_issue_valid_latitude"),
        CheckConstraint("location_lng >= -180.0 AND location_lng <= 180.0", name="chk_issue_valid_longitude"),
    )

    # Validations & Triggers
    @validates("description")
    def validate_description(self, key: str, value: str) -> str:
        """Auto-populate short_description from first 300 characters of description."""
        if value:
            clean_val = value.strip()
            self.short_description = clean_val[:300]
            return clean_val
        return value

    @validates("title")
    def validate_title(self, key: str, value: str) -> str:
        """Strip leading/trailing whitespace from title."""
        return value.strip() if value else value

    # Compatibility Properties
    @property
    def latitude(self) -> float:
        return self.location_lat

    @latitude.setter
    def latitude(self, val: float) -> None:
        self.location_lat = val

    @property
    def longitude(self) -> float:
        return self.location_lng

    @longitude.setter
    def longitude(self, val: float) -> None:
        self.location_lng = val

    @property
    def reporter(self) -> Optional["User"]:
        return self.reported_by

    @property
    def assignee(self) -> Optional["User"]:
        return self.assigned_to

    @property
    def resolver(self) -> Optional["User"]:
        return self.resolved_by

    # Model Instance Methods
    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, uuid='{self.uuid}', title='{self.title[:30]}', status='{self.status}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Return safe complete dictionary representation for API responses."""
        res: Dict[str, Any] = {}
        for column in self.__table__.columns:
            if column.name not in ("deleted_at", "ai_processed", "similarity_score"):
                val = getattr(self, column.name, None)
                if isinstance(val, uuid_pkg.UUID):
                    val = str(val)
                elif isinstance(val, datetime):
                    val = val.isoformat()
                elif isinstance(val, enum.Enum):
                    val = val.value
                res[column.name] = val
        res["uuid"] = str(self.uuid)
        res["days_open"] = self.days_open()
        return res

    def to_summary_dict(self) -> Dict[str, Any]:
        """Return minimal dictionary summary for list views."""
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "title": self.title,
            "short_description": self.short_description,
            "category": self.category.value if isinstance(self.category, enum.Enum) else self.category,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "priority": self.priority.value if isinstance(self.priority, enum.Enum) else self.priority,
            "location_lat": self.location_lat,
            "location_lng": self.location_lng,
            "location_address": self.location_address,
            "location_city": self.location_city,
            "image_url": self.image_url,
            "vote_count": self.vote_count,
            "comment_count": self.comment_count,
            "view_count": self.view_count,
            "days_open": self.days_open(),
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

    def to_map_dict(self) -> Dict[str, Any]:
        """Return compact dictionary representation tailored for map markers."""
        return {
            "uuid": str(self.uuid),
            "title": self.title,
            "status": self.status.value if isinstance(self.status, enum.Enum) else self.status,
            "priority": self.priority.value if isinstance(self.priority, enum.Enum) else self.priority,
            "category": self.category.value if isinstance(self.category, enum.Enum) else self.category,
            "location_lat": self.location_lat,
            "location_lng": self.location_lng,
            "vote_count": self.vote_count,
        }

    def is_resolved(self) -> bool:
        """Check if issue has reached resolved status."""
        return self.status == IssueStatus.RESOLVED or str(self.status) == "resolved"

    def is_open(self) -> bool:
        """Check if issue is active and open (not resolved or rejected)."""
        status_val = self.status.value if isinstance(self.status, enum.Enum) else self.status
        return status_val not in ("resolved", "rejected", "duplicate")

    def days_open(self) -> int:
        """Calculate elapsed days since issue creation."""
        end_time = self.resolved_at if self.is_resolved() and self.resolved_at else datetime.utcnow()
        return max(0, (end_time - self.created_at).days)

    def increment_view(self) -> None:
        """Increment page view count by 1."""
        self.view_count += 1

    def update_vote_count(self, db) -> None:
        """Recalculate and update vote_count cached attribute from votes table."""
        from sqlalchemy import func
        count = db.query(func.count(Vote.id)).filter(Vote.issue_id == self.id).scalar() or 0
        self.vote_count = count

    def sync_vote_count(self, db) -> None:
        """Alias for update_vote_count."""
        self.update_vote_count(db)

    def update_comment_count(self, db) -> None:
        """Recalculate and update comment_count cached attribute from comments table."""
        from sqlalchemy import func
        count = db.query(func.count(Comment.id)).filter(Comment.issue_id == self.id, Comment.deleted_at == None).scalar() or 0
        self.comment_count = count

    def sync_comment_count(self, db) -> None:
        """Alias for update_comment_count."""
        self.update_comment_count(db)

    @property
    def duplicate_of(self) -> Optional[int]:
        return self.duplicate_of_id

    def can_be_edited_by(self, user) -> bool:
        """Check if user is authorized to edit issue details."""
        if not user or not user.is_active:
            return False
        return user.is_admin() or (self.reporter_id == user.id)

    def can_status_be_updated_by(self, user) -> bool:
        """Check if user is authorized to update resolution status."""
        if not user or not user.is_active:
            return False
        return user.is_authority() or user.is_admin()


class Comment(Base):
    """Discussion Comment ORM model on community issues."""

    __tablename__ = "comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(GUID(), default=uuid_pkg.uuid4, unique=True, index=True, nullable=False)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    comment_type: Mapped[CommentType] = mapped_column(SQLEnum(CommentType, name="comment_type"), default=CommentType.CITIZEN_COMMENT, nullable=False)

    is_pinned: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("comments.id", ondelete="CASCADE"), nullable=True)
    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="comments", lazy="select")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="comments", lazy="select")
    replies: Mapped[List["Comment"]] = relationship("Comment", back_populates="parent", cascade="all, delete-orphan", lazy="select")
    parent: Mapped[Optional["Comment"]] = relationship("Comment", back_populates="replies", remote_side=[id], lazy="select")

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, uuid='{self.uuid}', issue_id={self.issue_id}, user_id={self.user_id})>"

    def to_dict(self) -> Dict[str, Any]:
        """Return clean dictionary representation excluding soft delete field."""
        return {
            "uuid": str(self.uuid),
            "issue_id": self.issue_id,
            "content": self.content,
            "comment_type": self.comment_type.value if isinstance(self.comment_type, enum.Enum) else self.comment_type,
            "is_pinned": self.is_pinned,
            "is_edited": self.is_edited,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "like_count": self.like_count,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def can_be_edited_by(self, user) -> bool:
        """Check if user is authorized to edit comment content."""
        if not user or not user.is_active:
            return False
        return user.is_admin() or (self.user_id == user.id)

    def can_be_deleted_by(self, user) -> bool:
        """Check if user is authorized to delete comment."""
        if not user or not user.is_active:
            return False
        return user.is_admin() or user.is_authority() or (self.user_id == user.id)


class Vote(Base):
    """Upvote ORM model representing user endorsement of an issue."""

    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    vote_type: Mapped[VoteType] = mapped_column(SQLEnum(VoteType, name="vote_type"), default=VoteType.UPVOTE, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="votes", lazy="select")
    user: Mapped["User"] = relationship("User", back_populates="votes", lazy="select")

    __table_args__ = (
        UniqueConstraint("issue_id", "user_id", name="unique_user_issue_vote"),
    )

    def __repr__(self) -> str:
        return f"<Vote(id={self.id}, issue_id={self.issue_id}, user_id={self.user_id}, vote_type='{self.vote_type}')>"

    def to_dict(self) -> Dict[str, Any]:
        """Return safe dictionary for API response."""
        return {
            "id": self.id,
            "issue_id": self.issue_id,
            "user_id": self.user_id,
            "vote_type": self.vote_type.value if isinstance(self.vote_type, enum.Enum) else self.vote_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class IssueHistory(Base):
    """Audit log model for tracking issue status and assignment changes."""

    __tablename__ = "issue_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True)
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(GUID(), default=uuid_pkg.uuid4, unique=True, index=True, nullable=False)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False, index=True)
    changed_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    change_type: Mapped[ChangeType] = mapped_column(SQLEnum(ChangeType, name="change_type"), nullable=False)
    old_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    new_value: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="history", lazy="select")
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[changed_by_id], lazy="select")

    def __repr__(self) -> str:
        return f"<IssueHistory(id={self.id}, issue_id={self.issue_id}, change_type='{self.change_type}')>"

    @property
    def changer(self) -> Optional["User"]:
        return self.user

    @property
    def changed_by(self) -> Optional["User"]:
        return self.user

    def to_dict(self) -> Dict[str, Any]:
        """Return safe dictionary for API response."""
        return {
            "uuid": str(self.uuid),
            "issue_id": self.issue_id,
            "change_type": self.change_type.value if isinstance(self.change_type, enum.Enum) else self.change_type,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "note": self.note,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
