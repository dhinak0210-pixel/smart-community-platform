"""Database ORM models package for Smart Community Platform.

NOTE ON IMPORT ORDER FOR ALEMBIC MIGRATIONS:
The import order in this file matters for Alembic autogenerate metadata tracking.
Base declarative models must be imported in dependency order (User first, as Issue, Vote, Comment, and Notification reference User via foreign keys).
Importing User, Issue, Comment, Vote, and IssueHistory here guarantees that Alembic registers all database tables and associated Enum types during migration autogeneration.
"""

from backend.models.user import User, UserRole
from backend.models.issue import (
    Issue,
    Comment,
    Vote,
    IssueHistory,
    IssueCategory,
    IssueStatus,
    IssuePriority,
    CommentType,
    VoteType,
    ChangeType,
)
from backend.models.notification import Notification
from backend.models.volunteer import VolunteerTask, TaskStatus

__all__ = [
    "User",
    "UserRole",
    "Issue",
    "Comment",
    "Vote",
    "IssueHistory",
    "IssueCategory",
    "IssueStatus",
    "IssuePriority",
    "CommentType",
    "VoteType",
    "ChangeType",
    "Notification",
    "VolunteerTask",
    "TaskStatus",
]
