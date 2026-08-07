"""User ORM database model with SQLAlchemy 2.0 mapping and security helpers."""

from __future__ import annotations
from datetime import datetime
import enum
import uuid as uuid_pkg
from typing import Optional, List, Dict, Any, TYPE_CHECKING

from sqlalchemy import (
    String, Integer, Float, Boolean, DateTime, Enum as SQLEnum, Index, CheckConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates
from backend.models.issue import GUID

from backend.database import Base

if TYPE_CHECKING:
    from backend.models.issue import Issue, Comment, Vote
    from backend.models.notification import Notification


class UserRole(str, enum.Enum):
    """Enumeration of access control roles within the Smart Community Platform."""
    CITIZEN = "citizen"
    VOLUNTEER = "volunteer"
    AUTHORITY = "authority"
    ADMIN = "admin"
    MODERATOR = "moderator"


class User(Base):
    """Production-ready SQLAlchemy 2.0 User database model for Smart Community Platform."""

    __tablename__ = "users"

    # Core Fields
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True, index=True, comment="Primary key integer ID")
    uuid: Mapped[uuid_pkg.UUID] = mapped_column(GUID(), default=uuid_pkg.uuid4, unique=True, index=True, nullable=False, comment="Public unique UUID for API responses")
    name: Mapped[str] = mapped_column(String(100), nullable=False, comment="User full name (stripped of whitespace)")
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False, comment="User email address (always lowercase)")
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False, comment="Bcrypt password hash (never returned in API responses)")
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, comment="Optional contact phone number")
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Optional profile image URL")
    bio: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="Optional short bio description")

    # Role and Permission Fields
    role: Mapped[UserRole] = mapped_column(SQLEnum(UserRole, name="user_role"), default=UserRole.CITIZEN, nullable=False, index=True, comment="Platform authorization role")

    # Status Fields
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True, comment="Account active status (False = soft banned)")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Email verification status")
    is_online: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, comment="Current online status")

    # Location Fields
    location_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Latitude coordinate (-90 to 90)")
    location_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="Longitude coordinate (-180 to 180)")
    location_city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="City name")
    location_area: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, comment="Area or neighborhood name")
    location_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Full street address")

    # Statistics Fields (auto-updated by system events)
    total_issues_reported: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Total issues submitted by user")
    total_issues_resolved: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Total issues resolved by user")
    total_votes_given: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Total upvotes cast by user")
    total_comments: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Total comments posted by user")
    reputation_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False, comment="Gamified reputation score calculated from activity")

    # Security & Account Lockout Fields
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Timestamp of most recent successful login")
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, comment="IP address of last login (IPv4 or IPv6)")
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False, comment="Consecutive failed login attempts count")
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Timestamp until which account remains locked")
    password_reset_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Temporary token for password reset")
    password_reset_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Expiration time for password reset token")
    email_verification_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Temporary token for email verification")

    # Timestamp Fields
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False, index=True, comment="Record creation timestamp")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False, comment="Record last updated timestamp")
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="Soft delete timestamp")

    # ORM Relationships
    issues_reported: Mapped[List["Issue"]] = relationship(
        "Issue",
        foreign_keys="Issue.reporter_id",
        back_populates="reported_by",
        cascade="all, delete-orphan",
    )
    issues_assigned: Mapped[List["Issue"]] = relationship(
        "Issue",
        foreign_keys="Issue.assigned_to_id",
        back_populates="assigned_to",
    )
    comments: Mapped[List["Comment"]] = relationship(
        "Comment",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    votes: Mapped[List["Vote"]] = relationship(
        "Vote",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[List["Notification"]] = relationship(
        "Notification",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Table Configuration and Database Constraints
    __table_args__ = (
        Index("ix_users_email_unique", "email", unique=True),
        Index("ix_users_uuid_unique", "uuid", unique=True),
        Index("ix_users_role_filter", "role"),
        Index("ix_users_is_active_filter", "is_active"),
        Index("ix_users_created_at_sort", "created_at"),
        CheckConstraint("location_lat >= -90.0 AND location_lat <= 90.0", name="chk_valid_latitude"),
        CheckConstraint("location_lng >= -180.0 AND location_lng <= 180.0", name="chk_valid_longitude"),
        CheckConstraint("reputation_score >= 0.0", name="chk_non_negative_reputation"),
        {"comment": "User accounts table storing core profile, security, roles, location, and reputation metrics."}
    )

    # Field Validators
    @validates("email")
    def validate_email(self, key: str, address: str) -> str:
        """Ensure email addresses are stripped and stored in lowercase."""
        if address:
            return address.strip().lower()
        return address

    @validates("name")
    def validate_name(self, key: str, name: str) -> str:
        """Ensure names are stripped of leading and trailing whitespace."""
        if name:
            return name.strip()
        return name

    @validates("location_lat")
    def validate_lat(self, key: str, lat: Optional[float]) -> Optional[float]:
        """Validate latitude range between -90 and 90 degrees."""
        if lat is not None and not (-90.0 <= lat <= 90.0):
            raise ValueError("Latitude must be between -90.0 and 90.0 degrees")
        return lat

    @validates("location_lng")
    def validate_lng(self, key: str, lng: Optional[float]) -> Optional[float]:
        """Validate longitude range between -180 and 180 degrees."""
        if lng is not None and not (-180.0 <= lng <= 180.0):
            raise ValueError("Longitude must be between -180.0 and 180.0 degrees")
        return lng

    # Model Instance Methods
    def __repr__(self) -> str:
        """Return clean string representation of the User instance."""
        return (
            f"<User(id={self.id}, uuid='{self.uuid}', email='{self.email}', "
            f"role='{self.role}', is_active={self.is_active})>"
        )

    def to_dict(self) -> Dict[str, Any]:
        """Return safe dictionary representation excluding sensitive auth and security fields."""
        sensitive_fields = {
            "password_hash",
            "password_reset_token",
            "password_reset_expires",
            "email_verification_token",
            "failed_login_attempts",
            "locked_until",
            "last_login_ip",
        }
        res: Dict[str, Any] = {}
        for column in self.__table__.columns:
            if column.name not in sensitive_fields:
                val = getattr(self, column.name, None)
                if isinstance(val, uuid_pkg.UUID):
                    val = str(val)
                elif isinstance(val, datetime):
                    val = val.isoformat()
                elif isinstance(val, UserRole):
                    val = val.value
                res[column.name] = val
        return res

    def to_public_dict(self) -> Dict[str, Any]:
        """Return minimal public user information dictionary."""
        return {
            "id": self.id,
            "uuid": str(self.uuid) if isinstance(self.uuid, uuid_pkg.UUID) else self.uuid,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "role": self.role.value if isinstance(self.role, UserRole) else self.role,
            "reputation_score": self.reputation_score,
        }

    def is_locked(self) -> bool:
        """Check if account is currently locked due to failed login attempts."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until

    def is_admin(self) -> bool:
        """Check if user has admin privileges."""
        return self.role == UserRole.ADMIN or str(self.role) == "admin"

    def is_authority(self) -> bool:
        """Check if user has authority or admin privileges."""
        role_str = str(self.role.value if isinstance(self.role, UserRole) else self.role)
        return role_str in ("authority", "admin")

    def can_update_issue_status(self) -> bool:
        """Check if user has permission to update issue status (authority or admin)."""
        return self.is_authority()

    def increment_reputation(self, points: float) -> None:
        """Increase user reputation score by given points."""
        if points > 0:
            self.reputation_score = round(self.reputation_score + points, 2)

    def decrement_reputation(self, points: float) -> None:
        """Decrease user reputation score safely without dropping below zero."""
        if points > 0:
            self.reputation_score = max(0.0, round(self.reputation_score - points, 2))

    def add_reputation(self, points: float, reason: str = "") -> None:
        """Add or subtract reputation points safely."""
        if points >= 0:
            self.increment_reputation(points)
        else:
            self.decrement_reputation(abs(points))
