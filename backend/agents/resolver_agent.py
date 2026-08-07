"""Smart Community Platform - Resolver Agent (Case Manager)."""

import json
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
import httpx
from sqlalchemy import select, and_, func

from backend.config import settings
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ResolverAgent(BaseAgent):
    """The Case Manager Agent.
    
    Wakes up every 6 hours and:
    1. ESCALATION CHECK: Overdue issues escalation (reminders & admin escalation)
    2. REMINDER SYSTEM: Follow-up emails to assigned authorities
    3. STALE ISSUE CLOSURE: Auto-close pending_citizen issues after 7 days
    4. RESOLUTION RATE TRACKING: Department performance analytics
    5. PRIORITY BUMPING: Upvoted issue priority escalation
    6. VOLUNTEER ISSUE CLEANUP: Stale volunteer claim cleanup
    """

    agent_name = "resolver"
    agent_description = "Manages open issue lifecycle and escalations"

    def __init__(self, groq_api_key: str = None):
        super().__init__()
        self.api_key = groq_api_key or settings.GROQ_API_KEY

    def generate_resolution_plan(self, issue_id: int, title: str, category: str) -> Dict[str, Any]:
        """Generate a step-by-step resolution plan based on issue category."""
        if self.api_key and self.api_key.startswith("gsk_"):
            try:
                prompt = (
                    f"Create an official municipal dispatch and action plan for issue #{issue_id}:\n"
                    f"Title: {title}\n"
                    f"Category: {category}\n\n"
                    f"Respond strictly with a JSON object containing:\n"
                    f"- assigned_department (string)\n"
                    f"- resolution_steps (list of strings, 3-5 action items)\n"
                    f"- estimated_completion_hours (integer)"
                )
                resp = httpx.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                    json={
                        "model": "llama-3.3-70b-versatile",
                        "messages": [{"role": "user", "content": prompt}],
                        "temperature": 0.2,
                        "response_format": {"type": "json_object"}
                    },
                    timeout=8.0
                )
                if resp.status_code == 200:
                    content = resp.json()["choices"][0]["message"]["content"]
                    parsed = json.loads(content)
                    parsed["issue_id"] = issue_id
                    parsed["title"] = title
                    parsed["category"] = category
                    parsed["agent"] = "ResolverAgent (Groq LLM)"
                    logger.info(f"Groq LLM resolution plan generated for issue #{issue_id}")
                    return parsed
            except Exception as e:
                logger.warning(f"Groq LLM call failed in ResolverAgent, falling back to heuristic: {e}")

        # Deterministic Heuristic Fallback
        steps: List[str] = [
            f"Dispatch field inspection team to issue #{issue_id} site.",
            "Verify site safety and set up hazard warning markers.",
        ]

        cat_lower = category.lower()
        if "infrastructure" in cat_lower or "pothole" in cat_lower or "road" in cat_lower:
            department = "Department of Public Works"
            steps.extend([
                "Estimate required asphalt and resurfacing materials.",
                "Schedule heavy road maintenance crew for pavement repair.",
                "Conduct compaction quality inspection and reopen traffic lane."
            ])
            est_hours = 48
        elif "light" in cat_lower or "utility" in cat_lower or "power" in cat_lower:
            department = "Electrical & Utilities Division"
            steps.extend([
                "Inspect electrical wiring and transformer box.",
                "Replace faulty LED bulb / fuse unit.",
                "Verify nighttime illumination."
            ])
            est_hours = 24
        elif "water" in cat_lower or "flood" in cat_lower or "pipe" in cat_lower:
            department = "Water & Sanitation Authority"
            steps.extend([
                "Isolate main valve shutoff to halt active leakage.",
                "Replace ruptured pipe section and seal joints.",
                "Pressure test water supply line."
            ])
            est_hours = 12
        elif "waste" in cat_lower or "trash" in cat_lower:
            department = "Sanitation & Environmental Health"
            steps.extend([
                "Dispatch high-capacity waste collection vehicle.",
                "Clear accumulated refuse and sanitize site area.",
                "Inspect nearby municipal dumpsters."
            ])
            est_hours = 18
        else:
            department = "Municipal General Services"
            steps.extend([
                "Assign designated department technician.",
                "Execute corrective maintenance.",
                "Confirm resolution with citizen reporter."
            ])
            est_hours = 36

        return {
            "issue_id": issue_id,
            "title": title,
            "category": category,
            "assigned_department": department,
            "resolution_steps": steps,
            "estimated_completion_hours": est_hours,
            "agent": "ResolverAgent (Heuristic)",
        }

    def match_volunteers(
        self,
        issue_id: int,
        lat: float,
        lng: float,
        category: str,
        db: Any,
        radius_km: float = 10.0,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Match available volunteers based on proximity, skills, and past activity."""
        try:
            from backend.models.user import User, UserRole
            from backend.utils.issue_helpers import haversine_distance

            stmt = select(User).where(
                User.role == UserRole.VOLUNTEER,
                User.is_active == True
            )
            volunteers = db.execute(stmt).scalars().all()

            matched = []
            for vol in volunteers:
                dist = haversine_distance(lat, lng, 12.9716, 77.5946)
                if hasattr(vol, "latitude") and hasattr(vol, "longitude") and vol.latitude and vol.longitude:
                    dist = haversine_distance(lat, lng, vol.latitude, vol.longitude)

                skills = getattr(vol, "skills", []) or []
                category_skill_match = any(
                    s.lower() in category.lower() for s in skills
                ) or len(skills) == 0

                rep_pts = getattr(vol, "reputation_score", getattr(vol, "reputation_points", 0)) or 0
                score = max(0.0, 10.0 - dist) + (5.0 if category_skill_match else 0.0) + rep_pts * 0.05

                matched.append({
                    "volunteer_id": vol.id,
                    "uuid": str(vol.uuid),
                    "name": vol.name,
                    "email": vol.email,
                    "reputation_points": rep_pts,
                    "distance_km": round(dist, 2),
                    "match_score": round(score, 2)
                })

            matched.sort(key=lambda x: x["match_score"], reverse=True)
            return matched[:limit]
        except Exception as e:
            logger.error(f"Volunteer matching failed in ResolverAgent: {e}")
            return []

    async def execute(self, db) -> None:
        """Run all resolver checks."""
        system_user_id = self.get_system_user_id(db)

        self.logger.info("Resolver Agent starting checks...")

        await self._check_escalations(db, system_user_id)
        await self._close_stale_issues(db, system_user_id)
        await self._bump_popular_priorities(db, system_user_id)
        await self._cleanup_abandoned_claims(db, system_user_id)
        await self._check_resolution_rates(db)

        self.logger.info(
            f"Resolver Agent complete: {self.actions_taken} actions taken"
        )

    async def _check_escalations(self, db, system_user_id: int):
        """Find and escalate overdue issues."""
        from backend.models.issue import Issue, IssueStatus

        ESCALATION_RULES = {
            IssueStatus.UNDER_REVIEW: {
                "days": 3,
                "action": "send_reminder",
                "message": "This issue has been under review for {days} days. Please take action."
            },
            IssueStatus.ACKNOWLEDGED: {
                "days": 5,
                "action": "send_reminder",
                "message": "This issue was acknowledged {days} days ago but has no progress update."
            },
            IssueStatus.IN_PROGRESS: {
                "days": settings.AGENT_ESCALATION_DAYS,
                "action": "escalate_to_admin",
                "message": "This issue has been in progress for {days} days without resolution."
            },
            IssueStatus.ASSIGNED: {
                "days": 4,
                "action": "send_reminder",
                "message": "This issue was assigned {days} days ago but no progress has been made."
            }
        }

        now = datetime.utcnow()

        for status, rule in ESCALATION_RULES.items():
            threshold_date = now - timedelta(days=rule["days"])

            overdue_issues = db.execute(
                select(Issue)
                .where(
                    and_(
                        Issue.status == status,
                        Issue.updated_at < threshold_date,
                        Issue.deleted_at.is_(None)
                    )
                )
                .limit(20)
            ).scalars().all()

            for issue in overdue_issues:
                try:
                    days_in_status = (now - issue.updated_at).days

                    if rule["action"] == "send_reminder":
                        await self._send_escalation_reminder(
                            issue=issue,
                            db=db,
                            system_user_id=system_user_id,
                            message=rule["message"].format(days=days_in_status)
                        )

                    elif rule["action"] == "escalate_to_admin":
                        await self._escalate_to_admin(
                            issue=issue,
                            db=db,
                            system_user_id=system_user_id,
                            days_overdue=days_in_status
                        )

                    self.issues_processed += 1

                except Exception as e:
                    self.record_error(
                        f"Escalation failed for {issue.uuid}: {e}",
                        str(issue.uuid)
                    )

    async def _send_escalation_reminder(
        self,
        issue,
        db,
        system_user_id: int,
        message: str
    ):
        """Send reminder to assigned authority."""
        from backend.models.user import User
        from backend.models.issue import Comment, CommentType, ChangeType

        if not issue.assigned_to:
            return

        authority = db.execute(
            select(User).where(User.id == issue.assigned_to)
        ).scalar_one_or_none()

        if not authority:
            return

        comment = Comment(
            issue_id=issue.id,
            user_id=system_user_id,
            content=f"🔔 Automated reminder: {message}",
            comment_type=CommentType.SYSTEM_MESSAGE
        )
        db.add(comment)
        issue.comment_count += 1

        self.create_history_entry(
            db=db,
            issue_id=issue.id,
            system_user_id=system_user_id,
            change_type=ChangeType.AI_UPDATE,
            old_value=issue.status.value,
            new_value=issue.status.value,
            note=f"Resolver Agent sent reminder: {message}"
        )

        try:
            from backend.utils.email import send_email

            html_body = f"""
                <div style="font-family: sans-serif; max-width: 600px;">
                    <h2 style="color: #D97706;">⏰ Issue Reminder</h2>
                    <p>{message}</p>
                    <div style="background: #F8FAFC; padding: 16px; border-radius: 8px; margin: 16px 0;">
                        <strong>Issue:</strong> {issue.title}<br>
                        <strong>Category:</strong> {issue.category.value}<br>
                        <strong>Priority:</strong> {issue.priority.value}<br>
                        <strong>Location:</strong> {issue.location_address or 'Not specified'}<br>
                        <strong>Votes:</strong> {issue.vote_count}
                    </div>
                    <a href="{settings.FRONTEND_URL}/issue.html?uuid={issue.uuid}"
                       style="background: #2563EB; color: white; padding: 12px 24px;
                              text-decoration: none; border-radius: 6px; display: inline-block;">
                        View and Update Issue →
                    </a>
                    <p style="color: #64748B; font-size: 0.85rem; margin-top: 24px;">
                        This is an automated reminder from Smart Community Platform.
                    </p>
                </div>
            """

            send_email(
                to_email=authority.email,
                subject=f"⏰ Reminder: Issue needs attention - {issue.title[:50]}",
                html_body=html_body
            )
        except Exception as e:
            self.record_error(f"Reminder email failed: {e}")

        db.commit()

        self.record_action(
            f"Sent reminder for '{issue.title[:40]}'",
            {"issue_uuid": str(issue.uuid), "authority": authority.email}
        )

    async def _escalate_to_admin(
        self,
        issue,
        db,
        system_user_id: int,
        days_overdue: int
    ):
        """Escalate severely overdue issue to admin."""
        from backend.models.issue import IssuePriority, Comment, CommentType, ChangeType
        from backend.models.user import User, UserRole

        self.logger.warning(
            f"ESCALATING issue {issue.uuid}: in {issue.status.value} for {days_overdue} days"
        )

        old_priority = issue.priority.value
        if issue.priority != IssuePriority.CRITICAL:
            issue.priority = IssuePriority.CRITICAL

        comment = Comment(
            issue_id=issue.id,
            user_id=system_user_id,
            content=(
                f"🚨 ESCALATED: This issue has been in '{issue.status.value}' status for {days_overdue} days "
                f"without resolution. Priority has been raised to CRITICAL. Admin attention required."
            ),
            comment_type=CommentType.SYSTEM_MESSAGE,
            is_pinned=True
        )
        db.add(comment)
        issue.comment_count += 1

        self.create_history_entry(
            db=db,
            issue_id=issue.id,
            system_user_id=system_user_id,
            change_type=ChangeType.PRIORITY_CHANGE,
            old_value=old_priority,
            new_value="critical",
            note=f"Auto-escalated by Resolver Agent: {days_overdue} days overdue"
        )

        admin_users = db.execute(
            select(User).where(User.role == UserRole.ADMIN, User.is_active == True)
        ).scalars().all()

        for admin in admin_users:
            try:
                from backend.utils.email import send_email

                html_body = f"""
                    <div style="font-family: sans-serif; max-width: 600px;">
                        <h2 style="color: #DC2626;">🚨 Issue Escalated to Critical</h2>
                        <p>An issue has been automatically escalated due to {days_overdue} days without resolution.</p>
                        <div style="background: #FEF2F2; border: 1px solid #FECACA; padding: 16px; border-radius: 8px; margin: 16px 0;">
                            <strong>Issue:</strong> {issue.title}<br>
                            <strong>Status:</strong> {issue.status.value}<br>
                            <strong>Days Open:</strong> {days_overdue}<br>
                            <strong>Priority:</strong> Now CRITICAL<br>
                            <strong>Department:</strong> {issue.assigned_department or 'Unassigned'}<br>
                            <strong>Votes:</strong> {issue.vote_count}
                        </div>
                        <a href="{settings.FRONTEND_URL}/issue.html?uuid={issue.uuid}"
                           style="background: #DC2626; color: white; padding: 12px 24px;
                                  text-decoration: none; border-radius: 6px; display: inline-block;">
                            View Escalated Issue →
                        </a>
                    </div>
                """
                send_email(
                    to_email=admin.email,
                    subject=f"🚨 ESCALATED: {issue.title[:50]}",
                    html_body=html_body
                )
            except Exception as e:
                self.record_error(f"Admin escalation email failed: {e}")

        db.commit()

        self.record_action(
            f"Escalated to CRITICAL: '{issue.title[:40]}'",
            {
                "issue_uuid": str(issue.uuid),
                "days_overdue": days_overdue,
                "notified_admins": len(admin_users)
            }
        )

    async def _close_stale_issues(self, db, system_user_id: int):
        """Auto-close issues stuck in pending_citizen."""
        from backend.models.issue import Issue, IssueStatus, ChangeType, Comment, CommentType

        stale_count = 0
        stale_issues = db.execute(
            select(Issue)
            .where(
                and_(
                    Issue.status == IssueStatus.PENDING_CITIZEN,
                    Issue.updated_at < datetime.utcnow() - timedelta(days=settings.AGENT_AUTO_CLOSE_DAYS),
                    Issue.deleted_at.is_(None)
                )
            )
            .limit(30)
        ).scalars().all()

        for issue in stale_issues:
            try:
                issue.status = IssueStatus.RESOLVED
                issue.citizen_confirmed_resolved = True
                issue.resolution_note = (
                    issue.resolution_note or "Auto-resolved: No citizen response within 7 days."
                )
                if not issue.resolved_at:
                    issue.resolved_at = datetime.utcnow()

                comment = Comment(
                    issue_id=issue.id,
                    user_id=system_user_id,
                    content=(
                        "✅ This issue has been automatically closed after 7 days in 'Awaiting Confirmation' "
                        "status with no response from the reporter. If the issue persists, please submit a new report."
                    ),
                    comment_type=CommentType.SYSTEM_MESSAGE
                )
                db.add(comment)
                issue.comment_count += 1

                self.create_history_entry(
                    db=db,
                    issue_id=issue.id,
                    system_user_id=system_user_id,
                    change_type=ChangeType.STATUS_CHANGE,
                    old_value="pending_citizen",
                    new_value="resolved",
                    note="Auto-closed by Resolver Agent: 7 days without citizen response"
                )

                stale_count += 1
                self.issues_processed += 1

                from backend.models.user import User

                reporter = db.execute(
                    select(User).where(User.id == issue.reported_by)
                ).scalar_one_or_none()
                if reporter:
                    if hasattr(reporter, "increment_reputation"):
                        reporter.increment_reputation(10)
                    elif hasattr(reporter, "reputation_score"):
                        reporter.reputation_score += 10
                    if hasattr(reporter, "total_issues_resolved"):
                        reporter.total_issues_resolved += 1

            except Exception as e:
                self.record_error(f"Stale close failed for {issue.uuid}: {e}")

        if stale_count > 0:
            db.commit()
            self.record_action(
                f"Auto-closed {stale_count} stale issues",
                {"count": stale_count}
            )

    async def _bump_popular_priorities(self, db, system_user_id: int):
        """Bump priority of issues with many votes but low priority."""
        from backend.models.issue import Issue, IssueStatus, IssuePriority, ChangeType

        VOTE_THRESHOLDS = {
            IssuePriority.LOW: (10, IssuePriority.MEDIUM),
            IssuePriority.MEDIUM: (25, IssuePriority.HIGH),
            IssuePriority.HIGH: (50, IssuePriority.CRITICAL)
        }

        bumped = 0
        for from_priority, (threshold, to_priority) in VOTE_THRESHOLDS.items():
            popular_issues = db.execute(
                select(Issue)
                .where(
                    and_(
                        Issue.priority == from_priority,
                        Issue.vote_count >= threshold,
                        Issue.manual_priority_override == False,
                        Issue.status.notin_([
                            IssueStatus.RESOLVED,
                            IssueStatus.REJECTED,
                            IssueStatus.DUPLICATE
                        ]),
                        Issue.deleted_at.is_(None)
                    )
                )
                .limit(10)
            ).scalars().all()

            for issue in popular_issues:
                try:
                    old_priority = issue.priority.value
                    issue.priority = to_priority

                    self.create_history_entry(
                        db=db,
                        issue_id=issue.id,
                        system_user_id=system_user_id,
                        change_type=ChangeType.PRIORITY_CHANGE,
                        old_value=old_priority,
                        new_value=to_priority.value,
                        note=f"Priority bumped by Resolver Agent: {issue.vote_count} community votes"
                    )
                    bumped += 1
                    self.issues_processed += 1
                except Exception as e:
                    self.record_error(f"Priority bump failed: {e}")

        if bumped > 0:
            db.commit()
            self.record_action(
                f"Bumped priority for {bumped} popular issues",
                {"count": bumped}
            )

    async def _cleanup_abandoned_claims(self, db, system_user_id: int):
        """Find and handle abandoned volunteer claims."""
        from backend.models.volunteer import VolunteerClaim

        abandoned = db.execute(
            select(VolunteerClaim)
            .where(
                and_(
                    VolunteerClaim.status == "claimed",
                    VolunteerClaim.claimed_at < (datetime.utcnow() - timedelta(days=3))
                )
            )
            .limit(20)
        ).scalars().all()

        for claim in abandoned:
            try:
                claim.status = "abandoned"
                self.record_action(
                    f"Marked volunteer claim as abandoned",
                    {"claim_id": claim.id, "volunteer_id": claim.volunteer_id}
                )
            except Exception as e:
                self.record_error(f"Claim cleanup failed: {e}")

        if abandoned:
            db.commit()

    async def _check_resolution_rates(self, db):
        """Calculate and log department resolution rates."""
        from backend.models.issue import Issue, IssueStatus

        last_30_days = datetime.utcnow() - timedelta(days=30)
        dept_stats = {}

        issues = db.execute(
            select(
                Issue.assigned_department,
                Issue.status,
                func.count(Issue.id).label("count")
            )
            .where(
                and_(
                    Issue.created_at >= last_30_days,
                    Issue.assigned_department.isnot(None),
                    Issue.deleted_at.is_(None)
                )
            )
            .group_by(Issue.assigned_department, Issue.status)
        ).all()

        for row in issues:
            dept = row.assigned_department
            if dept not in dept_stats:
                dept_stats[dept] = {"total": 0, "resolved": 0}
            dept_stats[dept]["total"] += row.count
            if row.status == IssueStatus.RESOLVED:
                dept_stats[dept]["resolved"] += row.count

        dept_rates = {}
        for dept, stats in dept_stats.items():
            if stats["total"] > 0:
                rate = stats["resolved"] / stats["total"] * 100
                dept_rates[dept] = {
                    "total": stats["total"],
                    "resolved": stats["resolved"],
                    "rate": round(rate, 1)
                }

        self.details["department_resolution_rates"] = dept_rates

        for dept, data in dept_rates.items():
            if data["rate"] < 30 and data["total"] >= 5:
                self.logger.warning(
                    f"Low resolution rate: {dept} = {data['rate']}% ({data['resolved']}/{data['total']} issues)"
                )
