"""Community Analytics & Dashboard endpoints."""

from typing import Dict, Any
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.issue import Issue, IssueStatus, IssueCategory
from backend.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard & Analytics"])


@router.get("/stats", response_model=Dict[str, Any])
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Retrieve community metrics, category distributions, and resolution statistics."""
    total_issues = db.query(func.count(Issue.id)).scalar() or 0
    resolved_issues = db.query(func.count(Issue.id)).filter(Issue.status == IssueStatus.RESOLVED).scalar() or 0
    in_progress_issues = db.query(func.count(Issue.id)).filter(Issue.status == IssueStatus.IN_PROGRESS).scalar() or 0
    reported_issues = db.query(func.count(Issue.id)).filter(Issue.status == IssueStatus.REPORTED).scalar() or 0
    total_users = db.query(func.count(User.id)).scalar() or 0

    # Category breakdown
    category_counts = db.query(
        Issue.category, func.count(Issue.id)
    ).group_by(Issue.category).all()

    category_stats = {cat.value if hasattr(cat, 'value') else str(cat): count for cat, count in category_counts}

    return {
        "summary": {
            "total_issues": total_issues,
            "resolved_issues": resolved_issues,
            "in_progress_issues": in_progress_issues,
            "reported_issues": reported_issues,
            "total_citizens": total_users,
            "resolution_rate": round((resolved_issues / total_issues * 100), 2) if total_issues > 0 else 0.0,
        },
        "by_category": category_stats,
    }
