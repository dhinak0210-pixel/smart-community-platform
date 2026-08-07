"""Volunteer task assignment, profile, and claim models for community resolution."""

from datetime import datetime
import enum
import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum, Float, Boolean, JSON
from sqlalchemy.orm import relationship
from backend.database import Base


class TaskStatus(str, enum.Enum):
    """Status of volunteer tasks."""
    OPEN = "open"
    ASSIGNED = "assigned"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class VolunteerTask(Base):
    """Volunteer Task model assigned to community volunteers."""
    __tablename__ = "volunteer_tasks"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), default=TaskStatus.OPEN, nullable=False)

    # Foreign Keys
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)
    volunteer_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    issue = relationship("Issue")
    volunteer = relationship("User")

    def __repr__(self) -> str:
        return f"<VolunteerTask(id={self.id}, title='{self.title}', status='{self.status}')>"


class VolunteerProfile(Base):
    """Profile details for registered volunteers."""
    __tablename__ = "volunteer_profiles"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)

    skills = Column(JSON, default=list, nullable=False)  # e.g. ["cleaning", "safety_training"]
    availability = Column(String(50), default="flexible", nullable=False)  # weekdays/weekends/both/flexible/evenings
    location_city = Column(String(100), nullable=True)
    location_area = Column(String(100), nullable=True)

    max_issues_at_once = Column(Integer, default=3, nullable=False)
    total_hours = Column(Float, default=0.0, nullable=False)
    issues_helped = Column(Integer, default=0, nullable=False)
    issues_completed = Column(Integer, default=0, nullable=False)
    rating = Column(Float, default=5.0, nullable=False)
    is_available = Column(Boolean, default=True, nullable=False)
    last_active = Column(DateTime, nullable=True)
    bio = Column(String(500), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = relationship("User")


class VolunteerClaim(Base):
    """Claim record when a volunteer takes on an issue task."""
    __tablename__ = "volunteer_claims"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    volunteer_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    issue_id = Column(Integer, ForeignKey("issues.id", ondelete="CASCADE"), nullable=False)

    status = Column(String(30), default="claimed", nullable=False)  # claimed, accepted, in_progress, completed, abandoned
    hours_spent = Column(Float, nullable=True, default=0.0)
    notes = Column(String(500), nullable=True)

    claimed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    accepted_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    rating_given = Column(Integer, nullable=True)  # 1-5
    feedback = Column(String(500), nullable=True)

    volunteer = relationship("User", foreign_keys=[volunteer_id])
    issue = relationship("Issue", foreign_keys=[issue_id])
