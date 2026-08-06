"""Volunteer task assignment and skill models for community resolution."""

from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Enum
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
