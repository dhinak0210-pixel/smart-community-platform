"""Agent audit log model for tracking autonomous agent runs and actions."""

from datetime import datetime
import uuid
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, Index
from backend.database import Base


class AgentLog(Base):
    """Execution log for autonomous AI agent tasks."""

    __tablename__ = "agent_logs"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, index=True, default=lambda: str(uuid.uuid4()))

    agent_name = Column(String(50), nullable=False, index=True)
    run_started_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    run_completed_at = Column(DateTime, nullable=True)

    status = Column(String(20), default="running", nullable=False, index=True)  # running, completed, failed, partial
    issues_processed = Column(Integer, default=0, nullable=False)
    actions_taken = Column(Integer, default=0, nullable=False)
    errors_encountered = Column(Integer, default=0, nullable=False)

    summary = Column(Text, nullable=True)
    details = Column(JSON, nullable=True)
    error_log = Column(Text, nullable=True)

    __table_args__ = (
        Index("idx_agent_log_name_start", "agent_name", "run_started_at"),
    )

    def __repr__(self) -> str:
        return f"<AgentLog(id={self.id}, agent='{self.agent_name}', status='{self.status}')>"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "uuid": str(self.uuid),
            "agent_name": self.agent_name,
            "run_started_at": self.run_started_at.isoformat() if self.run_started_at else None,
            "run_completed_at": self.run_completed_at.isoformat() if self.run_completed_at else None,
            "status": self.status,
            "issues_processed": self.issues_processed,
            "actions_taken": self.actions_taken,
            "errors_encountered": self.errors_encountered,
            "summary": self.summary,
            "details": self.details or {},
            "error_log": self.error_log,
        }
