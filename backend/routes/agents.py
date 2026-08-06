"""AI Agent endpoints for automated issue triaging and resolution plan generation."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.database import get_db
from backend.models.issue import Issue
from backend.agents import ReporterAgent, ResolverAgent, AnalystAgent, CommunityAgent
from backend.utils.auth import get_current_user
from backend.models.user import User, UserRole

router = APIRouter(prefix="/agents", tags=["AI Multi-Agents"])

reporter_agent = ReporterAgent()
resolver_agent = ResolverAgent()
analyst_agent = AnalystAgent()
community_agent = CommunityAgent()


@router.post("/triage/{issue_id}")
def triage_issue(
    issue_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run ReporterAgent to analyze issue severity and recommend priority level."""
    issue = db.execute(select(Issue).where(Issue.id == issue_id)).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")

    analysis = reporter_agent.analyze_report(
        title=issue.title,
        description=issue.description,
        category=issue.category.value if hasattr(issue.category, 'value') else str(issue.category)
    )
    return analysis


@router.post("/resolution-plan/{issue_id}")
def generate_resolution_plan(
    issue_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Run ResolverAgent to generate step-by-step dispatch action plan."""
    issue = db.execute(select(Issue).where(Issue.id == issue_id)).scalar_one_or_none()
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found.")

    plan = resolver_agent.generate_resolution_plan(
        issue_id=issue.id,
        title=issue.title,
        category=issue.category.value if hasattr(issue.category, 'value') else str(issue.category)
    )
    return plan
