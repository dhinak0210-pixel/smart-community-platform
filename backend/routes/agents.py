"""REST API routes for AI Agent management, auditing, citizen Q&A, and telemetry."""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.agent_log import AgentLog
from backend.agents.agent_scheduler import agent_scheduler
from backend.agents.community_agent import CommunityAgent
from backend.utils.auth import get_current_user, require_admin, get_optional_user

router = APIRouter(prefix="/api/agents", tags=["AI Agents"])


class CitizenChatRequest(BaseModel):
    question: str = Field(..., min_length=2, max_length=500, description="Citizen question")


class CitizenChatResponse(BaseModel):
    answer: str
    confidence: str
    relevant_issues: list = []
    suggested_actions: list = []
    sources: list = []


@router.get("/status")
def get_agents_status(
    admin: User = Depends(require_admin)
):
    """Get overall AI agents status and scheduled jobs (Admin only)."""
    return agent_scheduler.get_status()


@router.post("/{agent_name}/trigger")
async def trigger_agent_manually(
    agent_name: str,
    admin: User = Depends(require_admin)
):
    """Trigger an AI agent execution immediately out-of-band (Admin only)."""
    try:
        result = await agent_scheduler.trigger_now(agent_name)
        return {
            "message": f"Agent '{agent_name}' executed successfully",
            "result": result
        }
    except ValueError as val_err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(val_err)
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute agent '{agent_name}': {str(err)}"
        )


@router.get("/logs")
def get_agent_logs(
    agent_name: Optional[str] = Query(None, description="Filter by agent name"),
    status: Optional[str] = Query(None, description="Filter by status (running, completed, partial, failed)"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get paginated agent execution logs (Admin only)."""
    query = select(AgentLog)

    if agent_name:
        query = query.where(AgentLog.agent_name == agent_name)
    if status:
        query = query.where(AgentLog.status == status)

    total = db.execute(
        select(func.count(AgentLog.id)).select_from(query.subquery())
    ).scalar() or 0

    logs = db.execute(
        query.order_by(AgentLog.run_started_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "logs": [log.to_dict() for log in logs]
    }


@router.get("/logs/{log_id}")
def get_agent_log_detail(
    log_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get single agent log entry with full details (Admin only)."""
    log = db.execute(
        select(AgentLog).where(AgentLog.id == log_id)
    ).scalar_one_or_none()

    if not log:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Agent log #{log_id} not found"
        )

    return log.to_dict()


@router.post("/chat", response_model=CitizenChatResponse)
async def citizen_ai_chat(
    body: CitizenChatRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user)
):
    """24/7 Citizen AI Assistant endpoint using RAG and CommunityAgent."""
    community_agent = CommunityAgent()
    user_id = current_user.id if current_user else None

    result = await community_agent.answer_question(
        question=body.question,
        user_id=user_id,
        db=db
    )

    return result


@router.get("/telemetry")
def get_agent_telemetry(
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin)
):
    """Get aggregate telemetry metrics for all AI agents (Admin only)."""
    total_runs = db.execute(select(func.count(AgentLog.id))).scalar() or 0

    completed_runs = db.execute(
        select(func.count(AgentLog.id)).where(AgentLog.status == "completed")
    ).scalar() or 0

    partial_runs = db.execute(
        select(func.count(AgentLog.id)).where(AgentLog.status == "partial")
    ).scalar() or 0

    failed_runs = db.execute(
        select(func.count(AgentLog.id)).where(AgentLog.status == "failed")
    ).scalar() or 0

    total_issues_processed = db.execute(
        select(func.sum(AgentLog.issues_processed))
    ).scalar() or 0

    total_actions_taken = db.execute(
        select(func.sum(AgentLog.actions_taken))
    ).scalar() or 0

    total_errors = db.execute(
        select(func.sum(AgentLog.errors_encountered))
    ).scalar() or 0

    agent_breakdown = db.execute(
        select(
            AgentLog.agent_name,
            func.count(AgentLog.id).label("runs"),
            func.sum(AgentLog.issues_processed).label("issues"),
            func.sum(AgentLog.actions_taken).label("actions"),
            func.sum(AgentLog.errors_encountered).label("errors")
        )
        .group_by(AgentLog.agent_name)
    ).all()

    breakdown = {}
    for row in agent_breakdown:
        breakdown[row.agent_name] = {
            "runs": row.runs,
            "issues_processed": row.issues or 0,
            "actions_taken": row.actions or 0,
            "errors": row.errors or 0
        }

    return {
        "summary": {
            "total_runs": total_runs,
            "completed_runs": completed_runs,
            "partial_runs": partial_runs,
            "failed_runs": failed_runs,
            "success_rate_percent": round((completed_runs / max(1, total_runs)) * 100, 1),
            "total_issues_processed": total_issues_processed,
            "total_actions_taken": total_actions_taken,
            "total_errors": total_errors
        },
        "by_agent": breakdown
    }
