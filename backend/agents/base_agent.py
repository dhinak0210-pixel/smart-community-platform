"""Base class for all Smart Community Platform autonomous AI agents."""

import logging
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from backend.database import SessionLocal
from backend.models.agent_log import AgentLog
from backend.config import settings


class BaseAgent:
    """Base class for all Smart Community Platform agents.
    
    Every agent:
    - Has a name and description
    - Creates its own DB session per run
    - Logs every run to agent_logs table
    - Never crashes the application
    - Reports what it did in human-readable summary
    - Has configurable retry logic
    """

    agent_name: str = "base_agent"
    agent_description: str = "Base agent"
    max_retries: int = settings.AGENT_MAX_RETRIES

    def __init__(self):
        self.logger = logging.getLogger(f"agents.{self.agent_name}")
        self.current_log: Optional[AgentLog] = None
        self.actions_taken: int = 0
        self.issues_processed: int = 0
        self.errors: List[str] = []
        self.details: Dict[str, Any] = {}

    async def run(self) -> dict:
        """Main entry point for every agent run.
        
        Called by APScheduler on schedule.
        Never raises exceptions.
        Returns run summary dict.
        """
        self.logger.info(f"Agent {self.agent_name} starting run...")
        run_start = datetime.utcnow()
        self.actions_taken = 0
        self.issues_processed = 0
        self.errors = []
        self.details = {}

        db = SessionLocal()

        log_entry = AgentLog(
            agent_name=self.agent_name,
            run_started_at=run_start,
            status="running"
        )
        db.add(log_entry)
        db.commit()
        db.refresh(log_entry)
        self.current_log = log_entry

        status = "running"
        try:
            await self.execute(db)
            status = "completed" if len(self.errors) == 0 else "partial"
        except Exception as e:
            status = "failed"
            error_msg = f"Agent {self.agent_name} failed: {str(e)}"
            self.logger.error(error_msg, exc_info=True)
            self.errors.append(error_msg)
        finally:
            summary = self._build_summary()

            log_entry.run_completed_at = datetime.utcnow()
            log_entry.status = status
            log_entry.issues_processed = self.issues_processed
            log_entry.actions_taken = self.actions_taken
            log_entry.errors_encountered = len(self.errors)
            log_entry.summary = summary
            log_entry.details = self.details
            if self.errors:
                log_entry.error_log = "\n".join(self.errors)

            try:
                db.commit()
            except Exception as save_err:
                self.logger.error(f"Failed to update AgentLog entry: {save_err}")
                db.rollback()
            finally:
                db.close()

            run_time = (datetime.utcnow() - run_start).total_seconds()
            self.logger.info(
                f"Agent {self.agent_name} finished: "
                f"status={status} "
                f"issues={self.issues_processed} "
                f"actions={self.actions_taken} "
                f"time={run_time:.1f}s"
            )

            return {
                "agent": self.agent_name,
                "status": status,
                "issues_processed": self.issues_processed,
                "actions_taken": self.actions_taken,
                "errors": len(self.errors),
                "run_time_seconds": run_time,
                "summary": summary
            }

    async def execute(self, db) -> None:
        """Override this in each agent. Contains agent logic."""
        raise NotImplementedError(
            f"Agent {self.agent_name} must implement execute()"
        )

    def record_action(self, action: str, details: dict = None):
        """Record an action taken by this agent."""
        if details is None:
            details = {}
        self.actions_taken += 1
        action_key = f"action_{self.actions_taken:03d}"
        self.details[action_key] = {
            "action": action,
            "timestamp": datetime.utcnow().isoformat(),
            **details
        }
        self.logger.info(f"Action: {action}")

    def record_error(self, error: str, issue_uuid: str = None):
        """Record a non-fatal error."""
        msg = f"Error{f' (issue {issue_uuid})' if issue_uuid else ''}: {error}"
        self.errors.append(msg)
        self.logger.warning(msg)

    def _build_summary(self) -> str:
        """Build human-readable run summary."""
        parts = [
            f"Processed {self.issues_processed} issues.",
            f"Took {self.actions_taken} actions."
        ]
        if self.errors:
            parts.append(f"Encountered {len(self.errors)} errors.")
        return " ".join(parts)

    async def retry_operation(self, func, *args, **kwargs) -> Any:
        """Retry an operation up to max_retries times.
        Waits 2^attempt seconds between retries.
        """
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                wait_time = 2 ** attempt
                self.logger.warning(
                    f"Attempt {attempt + 1} failed: {e}. "
                    f"Retrying in {wait_time}s..."
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(wait_time)
        return None

    def get_system_user_id(self, db) -> int:
        """Get or create system user for agent actions.
        Agents need a user_id for IssueHistory and Comment entries.
        """
        from backend.models.user import User, UserRole
        from backend.utils.auth import hash_password

        system_user = db.execute(
            select(User).where(User.email == "system@smartcommunity.internal")
        ).scalar_one_or_none()

        if not system_user:
            system_user = User(
                name="System Agent",
                email="system@smartcommunity.internal",
                password_hash=hash_password("SYSTEM_NO_LOGIN_123!"),
                role=UserRole.ADMIN,
                is_active=True,
                is_verified=True
            )
            db.add(system_user)
            db.commit()
            db.refresh(system_user)
            self.logger.info("Created system user for agent actions")

        return system_user.id

    def create_history_entry(
        self,
        db,
        issue_id: int,
        system_user_id: int,
        change_type,
        old_value: Optional[str],
        new_value: Optional[str],
        note: str
    ):
        """Create IssueHistory entry for agent action."""
        from backend.models.issue import IssueHistory
        history = IssueHistory(
            issue_id=issue_id,
            changed_by=system_user_id,
            change_type=change_type,
            old_value=str(old_value) if old_value is not None else None,
            new_value=str(new_value) if new_value is not None else None,
            note=note
        )
        db.add(history)
