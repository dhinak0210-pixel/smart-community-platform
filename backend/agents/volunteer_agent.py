"""Smart Community Platform - Volunteer Coordinator Agent (HR Manager)."""

import logging
from datetime import datetime
from typing import Dict, Any, List
from sqlalchemy import select, and_, func

from backend.config import settings
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class VolunteerCoordinatorAgent(BaseAgent):
    """The Volunteer HR Manager Agent.
    
    Runs every hour and:
    1. Finds high-priority issues needing volunteer help
    2. Finds available volunteers nearby
    3. Calculates match score (skills + location + availability)
    4. Sends match notifications to top volunteers
    5. Tracks volunteer performance metrics
    """

    agent_name = "volunteer_coordinator"
    agent_description = "Matches volunteers to issues and tracks their performance"

    SKILL_TO_CATEGORY_MAP = {
        "construction": ["infrastructure", "flooding"],
        "cleaning": ["waste", "environment"],
        "safety_training": ["safety"],
        "electrical": ["utilities"],
        "driving": ["traffic"],
        "first_aid": ["safety"],
        "tech": ["utilities"],
        "gardening": ["environment"],
        "general": ["other", "waste", "environment"]
    }

    async def execute(self, db) -> None:
        """Run volunteer matching."""
        self.logger.info("Volunteer Coordinator Agent starting...")

        issues_to_match = await self._find_matchable_issues(db)
        if not issues_to_match:
            self.logger.info("No matchable issues found this run")
            return

        self.logger.info(f"Found {len(issues_to_match)} issues needing volunteer match")

        available_volunteers = await self._get_available_volunteers(db)
        if not available_volunteers:
            self.logger.info("No available volunteers at this time")
            return

        self.logger.info(f"Found {len(available_volunteers)} available volunteers")

        for issue in issues_to_match:
            try:
                await self._match_issue_to_volunteers(
                    issue=issue,
                    volunteers=available_volunteers,
                    db=db
                )
                self.issues_processed += 1
            except Exception as e:
                self.record_error(f"Matching failed for {issue.uuid}: {e}")

        await self._update_volunteer_stats(db)
        self.logger.info("Volunteer Coordinator Agent complete")

    async def _find_matchable_issues(self, db) -> list:
        """Find issues that need volunteer matching."""
        from backend.models.issue import Issue, IssueStatus, IssuePriority

        return db.execute(
            select(Issue)
            .where(
                and_(
                    Issue.status.in_([
                        IssueStatus.ACKNOWLEDGED,
                        IssueStatus.ASSIGNED,
                        IssueStatus.IN_PROGRESS,
                        "acknowledged", "assigned", "in_progress"
                    ]),
                    Issue.priority.in_([
                        IssuePriority.CRITICAL,
                        IssuePriority.HIGH,
                        IssuePriority.MEDIUM,
                        "critical", "high", "medium"
                    ]),
                    Issue.deleted_at.is_(None)
                )
            )
            .order_by(Issue.priority.desc(), Issue.vote_count.desc())
            .limit(10)
        ).scalars().all()

    async def _get_available_volunteers(self, db) -> list:
        """Get volunteers who are available and active."""
        from backend.models.volunteer import VolunteerProfile
        from backend.models.user import User

        return db.execute(
            select(VolunteerProfile, User)
            .join(User, VolunteerProfile.user_id == User.id)
            .where(
                and_(
                    VolunteerProfile.is_available == True,
                    User.is_active == True
                )
            )
            .limit(100)
        ).all()

    async def _match_issue_to_volunteers(self, issue, volunteers: list, db):
        """Calculate match scores and notify top volunteers."""
        scored_volunteers = []

        for vol_profile, vol_user in volunteers:
            score = self._calculate_match_score(
                issue=issue,
                volunteer=vol_profile,
                volunteer_user=vol_user
            )

            if score >= settings.AGENT_MIN_VOLUNTEER_MATCH_SCORE:
                scored_volunteers.append({
                    "profile": vol_profile,
                    "user": vol_user,
                    "score": score
                })

        scored_volunteers.sort(key=lambda x: x["score"], reverse=True)
        top_matches = scored_volunteers[:3]

        if not top_matches:
            self.logger.info(f"No good volunteer matches for issue {issue.uuid}")
            return

        for match in top_matches:
            try:
                from backend.utils.email import send_volunteer_matched_email

                send_volunteer_matched_email(
                    to_email=match["user"].email,
                    volunteer_name=match["user"].name,
                    issue_title=issue.title,
                    issue_uuid=str(issue.uuid),
                    issue_location=issue.location_address or issue.location_city or "Unknown location"
                )

                self.record_action(
                    f"Volunteer matched: {match['user'].name} → '{issue.title[:30]}'",
                    {
                        "volunteer_uuid": str(match["user"].uuid),
                        "issue_uuid": str(issue.uuid),
                        "match_score": round(match["score"], 2)
                    }
                )
            except Exception as e:
                self.record_error(f"Volunteer notification failed: {e}", str(issue.uuid))

    def _calculate_match_score(self, issue, volunteer, volunteer_user) -> float:
        """Calculate how well a volunteer matches an issue.
        Returns score between 0.0 and 1.0.
        """
        score = 0.0

        volunteer_skills = volunteer.skills or []
        category = issue.category.value if hasattr(issue.category, "value") else str(issue.category)
        skill_score = 0.0

        for skill in volunteer_skills:
            compatible_categories = self.SKILL_TO_CATEGORY_MAP.get(skill, [])
            if category in compatible_categories:
                skill_score = 1.0
                break
            elif "general" in volunteer_skills:
                skill_score = 0.5

        score += skill_score * 0.4

        location_score = 0.0
        if (volunteer.location_city and issue.location_city and
                volunteer.location_city.lower() == issue.location_city.lower()):
            location_score = 1.0
        elif (volunteer.location_area and issue.location_area and
              volunteer.location_area.lower() == issue.location_area.lower()):
            location_score = 0.8
        elif volunteer.location_city and issue.location_city:
            location_score = 0.3

        score += location_score * 0.3

        availability_score = 0.7
        current_hour = datetime.utcnow().hour
        if volunteer.availability == "flexible":
            availability_score = 1.0
        elif volunteer.availability == "weekends":
            if datetime.utcnow().weekday() >= 5:
                availability_score = 1.0
            else:
                availability_score = 0.2
        elif volunteer.availability == "evenings":
            if 17 <= current_hour <= 22:
                availability_score = 1.0
            else:
                availability_score = 0.3

        score += availability_score * 0.15

        rating_score = (volunteer.rating or 5.0) / 5.0
        completion_rate = 1.0
        if volunteer.issues_helped > 0:
            completion_rate = volunteer.issues_completed / volunteer.issues_helped
        reliability = (rating_score + completion_rate) / 2.0
        score += reliability * 0.15

        return round(score, 3)

    async def _update_volunteer_stats(self, db):
        """Update volunteer performance metrics."""
        from backend.models.volunteer import VolunteerProfile, VolunteerClaim

        completed = db.execute(
            select(
                VolunteerClaim.volunteer_id,
                func.count(VolunteerClaim.id).label("completed_count"),
                func.sum(VolunteerClaim.hours_spent).label("total_hours"),
                func.avg(VolunteerClaim.rating_given).label("avg_rating")
            )
            .where(VolunteerClaim.status == "completed")
            .group_by(VolunteerClaim.volunteer_id)
        ).all()

        for row in completed:
            profile = db.execute(
                select(VolunteerProfile).where(VolunteerProfile.user_id == row.volunteer_id)
            ).scalar_one_or_none()

            if profile:
                profile.issues_completed = row.completed_count
                profile.total_hours = float(row.total_hours or 0.0)
                if row.avg_rating:
                    profile.rating = round(float(row.avg_rating), 2)

        db.commit()
        self.record_action("Updated volunteer performance stats")
