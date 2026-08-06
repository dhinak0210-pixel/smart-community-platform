"""User ORM database model with password hashing and helper methods."""

import uuid
from datetime import datetime
import enum
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum
from sqlalchemy.orm import relationship
from backend.database import Base
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class UserRole(str, enum.Enum):
    """Enumeration of user roles within the platform."""
    CITIZEN = "citizen"
    VOLUNTEER = "volunteer"
    AUTHORITY = "authority"
    ADMIN = "admin"


class User(Base):
    """User database model."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()), nullable=False)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=True)
    role = Column(Enum(UserRole), default=UserRole.CITIZEN, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    avatar_url = Column(String(500), nullable=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # ORM Relationships
    reported_issues = relationship(
        "Issue",
        foreign_keys="Issue.reporter_id",
        back_populates="reporter",
        cascade="all, delete-orphan",
    )
    assigned_issues = relationship(
        "Issue",
        foreign_keys="Issue.assigned_to_id",
        back_populates="assigned_to",
    )
    votes = relationship("Vote", back_populates="user", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")

    def verify_password(self, plain_password: str) -> bool:
        """Verify plain password against hashed password stored in DB."""
        return pwd_context.verify(plain_password, self.hashed_password)

    def set_password(self, plain_password: str) -> None:
        """Hash and set the user's password."""
        self.hashed_password = pwd_context.hash(plain_password)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, uuid='{self.uuid}', email='{self.email}', role='{self.role}')>"
