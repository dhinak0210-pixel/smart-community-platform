"""Issue, Vote, and Comment ORM database models."""

from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Text, Float, DateTime, ForeignKey, Enum, UniqueConstraint
from sqlalchemy.orm import relationship
from backend.database import Base


class IssueStatus(str, enum.Enum):
    """Status options for reported community issues."""
    REPORTED = "reported"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    REJECTED = "rejected"


class IssuePriority(str, enum.Enum):
    """Priority levels for issues."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class IssueCategory(str, enum.Enum):
    """Categories for community issues."""
    POTHOLE = "pothole"
    STREET_LIGHT = "street_light"
    WATER_SUPPLY = "water_supply"
    WASTE_MANAGEMENT = "waste_management"
    TRAFFIC_SIGNAL = "traffic_signal"
    PARK_MAINTENANCE = "park_maintenance"
    OTHER = "other"


class Issue(Base):
    """Community Issue database model."""
    __tablename__ = "issues"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    category = Column(Enum(IssueCategory), default=IssueCategory.OTHER, index=True, nullable=False)
    status = Column(Enum(IssueStatus), default=IssueStatus.REPORTED, index=True, nullable=False)
    priority = Column(Enum(IssuePriority), default=IssuePriority.MEDIUM, nullable=False)
    
    # Location coordinates & address
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    address = Column(String(255), nullable=True)
    
    # Media attachment
    image_url = Column(String(500), nullable=True)
    
    # Foreign Keys
    reporter_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    assigned_to_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    reporter = relationship("User", foreign_keys=[reporter_id], back_populates="reported_issues")
    assigned_to = relationship("User", foreign_keys=[assigned_to_id], back_populates="assigned_issues")
    votes = relationship("Vote", back_populates="issue", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="issue", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Issue(id={self.id}, title='{self.title}', status='{self.status}')>"


class Vote(Base):
    """Upvote model for issues."""
    __tablename__ = "votes"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Prevent duplicate votes by same user on same issue
    __table_args__ = (
        UniqueConstraint("issue_id", "user_id", name="unique_user_issue_vote"),
    )

    # Relationships
    issue = relationship("Issue", back_populates="votes")
    user = relationship("User", back_populates="votes")


class Comment(Base):
    """Community discussion comment model on issues."""
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationships
    issue = relationship("Issue", back_populates="comments")
    user = relationship("User", back_populates="comments")
