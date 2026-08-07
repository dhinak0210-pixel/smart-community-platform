"""Multi-Agent Orchestration Engine for Smart Community Platform.

Coordinates autonomous agent tasks across ReporterAgent, ResolverAgent, AnalystAgent,
and CommunityAgent for issue triage, dispatch planning, reputation awards, and analytics.
"""

import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.agents.reporter_agent import ReporterAgent
from backend.agents.resolver_agent import ResolverAgent
from backend.agents.analyst_agent import AnalystAgent
from backend.agents.community_agent import CommunityAgent
from backend.models.issue import Issue
from backend.models.volunteer import VolunteerTask, TaskStatus

logger = logging.getLogger(__name__)


class MultiAgentOrchestrator:
    """Orchestrator managing multi-agent collaboration workflows."""

    def __init__(self):
        self.reporter = ReporterAgent()
        self.resolver = ResolverAgent()
        self.analyst = AnalystAgent()
        self.community = CommunityAgent()

    def process_issue_workflow(
        self,
        issue_id: int,
        db: Session,
        auto_assign_volunteer: bool = True
    ) -> Dict[str, Any]:
        """Execute full 4-agent workflow for a newly reported or triaged issue."""
        logger.info(f"MultiAgentOrchestrator starting workflow for Issue #{issue_id}")

        stmt = select(Issue).where(Issue.id == issue_id)
        issue = db.execute(stmt).scalar_one_or_none()

        if not issue:
            logger.error(f"Issue #{issue_id} not found for multi-agent workflow")
            return {"success": False, "error": f"Issue {issue_id} not found"}

        cat_str = issue.category.value if hasattr(issue.category, "value") else str(issue.category)

        # 1. ReporterAgent: Triage & Urgency Assessment
        triage = self.reporter.analyze_report(
            title=issue.title,
            description=issue.description,
            category=cat_str
        )

        # 2. ResolverAgent: Resolution Dispatch Plan & Volunteer Matching
        resolution_plan = self.resolver.generate_resolution_plan(
            issue_id=issue.id,
            title=issue.title,
            category=cat_str
        )

        volunteer_matches = self.resolver.match_volunteers(
            issue_id=issue.id,
            lat=issue.location_lat,
            lng=issue.location_lng,
            category=cat_str,
            db=db
        )

        # Auto-create volunteer task if appropriate
        created_task = None
        if auto_assign_volunteer and volunteer_matches:
            top_vol = volunteer_matches[0]
            existing_task = db.execute(
                select(VolunteerTask).where(VolunteerTask.issue_id == issue.id)
            ).scalar_one_or_none()

            if not existing_task:
                new_task = VolunteerTask(
                    issue_id=issue.id,
                    title=f"Verify & Assist: {issue.title}",
                    description=f"Action items: {', '.join(resolution_plan.get('resolution_steps', [])[:2])}",
                    volunteer_id=top_vol["volunteer_id"],
                    status=TaskStatus.ASSIGNED,
                )
                db.add(new_task)
                db.commit()
                db.refresh(new_task)
                created_task = {
                    "task_id": new_task.id,
                    "assigned_volunteer": top_vol["name"]
                }

        # 3. CommunityAgent: Award Reporter Reputation Points
        rep_reward = 5
        if triage.get("urgency_score", 0) > 7.0:
            rep_reward = 10

        if issue.reporter:
            issue.reporter.add_reputation(rep_reward, reason="Detailed community issue report")

        # Update issue fields with resolution plan info
        if not issue.assigned_department and resolution_plan.get("assigned_department"):
            issue.assigned_department = resolution_plan["assigned_department"]

        db.commit()

        summary = {
            "issue_id": issue.id,
            "issue_uuid": str(issue.uuid),
            "triage": triage,
            "resolution_plan": resolution_plan,
            "volunteer_matches": volunteer_matches,
            "created_volunteer_task": created_task,
            "reporter_rewarded_points": rep_reward,
            "status": "completed"
        }

        logger.info(f"MultiAgentOrchestrator workflow completed for Issue #{issue_id}")
        return summary


# Global instance
orchestrator = MultiAgentOrchestrator()
