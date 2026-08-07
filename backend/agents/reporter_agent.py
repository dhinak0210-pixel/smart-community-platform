"""Smart Community Platform - Reporter Agent (Intake Coordinator)."""

import json
import logging
from datetime import datetime
from typing import Dict, Any
import httpx
from sqlalchemy import select, and_

from backend.config import settings
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class ReporterAgent(BaseAgent):
    """The Intake Coordinator Agent.
    
    Wakes up every 5 minutes and:
    1. Finds all issues where ai_processed = False
    2. For each issue:
       a. Runs full AI pipeline (text + image analysis)
       b. Detects if it is a duplicate
       c. Routes to correct department based on category
       d. Sets initial priority & tags
       e. Adds system comment
       f. Sends notification to reporter
    3. Logs everything it did
    """

    agent_name = "reporter"
    agent_description = "Processes new issues and routes them to departments"

    DEPARTMENT_ROUTING = {
        "infrastructure": "Roads and Infrastructure Department",
        "waste": "Waste Management Department",
        "safety": "Public Safety Department",
        "environment": "Environmental Services Department",
        "utilities": "Utilities Department",
        "traffic": "Traffic Management Department",
        "noise": "Community Standards Department",
        "flooding": "Drainage and Flooding Department",
        "other": "General Services Department"
    }

    def __init__(self, groq_api_key: str = None):
        super().__init__()
        self.api_key = groq_api_key or settings.GROQ_API_KEY

    def analyze_report(self, title: str, description: str, category: str) -> Dict[str, Any]:
        """Analyze issue report text and recommend priority level and urgency keywords."""
        if self.api_key and self.api_key.startswith("gsk_"):
            try:
                prompt = (
                    f"Analyze this community issue report:\n"
                    f"Title: {title}\n"
                    f"Description: {description}\n"
                    f"Category: {category}\n\n"
                    f"Respond strictly with a JSON object containing:\n"
                    f"- recommended_priority (string: 'critical', 'high', 'medium', or 'low')\n"
                    f"- urgency_score (float 0-100)\n"
                    f"- detected_keywords (list of strings)\n"
                    f"- action_summary (string short explanation)"
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
                    parsed["title"] = title
                    parsed["category"] = category
                    parsed["agent"] = "ReporterAgent (Groq LLM)"
                    logger.info(f"Groq LLM triage successful for '{title}'")
                    return parsed
            except Exception as e:
                logger.warning(f"Groq LLM call failed in ReporterAgent, falling back to heuristic: {e}")

        # Deterministic Heuristic Fallback
        urgent_keywords = [
            "danger", "hazard", "overflow", "accident", "broken", "emergency", "fire",
            "flood", "collapse", "severe", "life-threatening", "exposed wire", "gas leak"
        ]
        text_lower = f"{title} {description}".lower()
        matched = [kw for kw in urgent_keywords if kw in text_lower]

        if len(matched) >= 3 or "emergency" in text_lower or "gas leak" in text_lower:
            recommended_priority = "critical"
            urgency_score = 95.0
        elif len(matched) >= 2:
            recommended_priority = "high"
            urgency_score = 80.0
        elif len(matched) == 1:
            recommended_priority = "high"
            urgency_score = 65.0
        else:
            recommended_priority = "medium"
            urgency_score = 45.0

        action_summary = (
            f"Issue auto-triaged with priority '{recommended_priority}'. "
            f"Detected {len(matched)} hazard indicators: {', '.join(matched) if matched else 'None'}."
        )

        return {
            "title": title,
            "category": category,
            "recommended_priority": recommended_priority,
            "urgency_score": urgency_score,
            "detected_keywords": matched,
            "action_summary": action_summary,
            "agent": "ReporterAgent (Heuristic)",
        }

    async def execute(self, db) -> None:
        """Main agent logic executed on schedule."""
        from backend.models.issue import Issue, IssueStatus

        unprocessed = db.execute(
            select(Issue)
            .where(
                and_(
                    Issue.ai_processed == False,
                    Issue.deleted_at.is_(None),
                    Issue.status == IssueStatus.REPORTED
                )
            )
            .order_by(Issue.created_at.asc())
            .limit(50)
        ).scalars().all()

        if not unprocessed:
            self.logger.info("Reporter Agent: No unprocessed issues found")
            return

        self.logger.info(
            f"Reporter Agent: Found {len(unprocessed)} unprocessed issues to handle"
        )

        system_user_id = self.get_system_user_id(db)

        for issue in unprocessed:
            try:
                await self._process_single_issue(issue, db, system_user_id)
                self.issues_processed += 1
            except Exception as e:
                self.record_error(str(e), str(issue.uuid))

        self.details["total_unprocessed"] = len(unprocessed)
        self.details["successfully_processed"] = self.issues_processed

    async def _process_single_issue(self, issue, db, system_user_id: int):
        """Process one issue through the complete reporter pipeline."""
        self.logger.info(
            f"Reporter processing issue: {issue.uuid} title='{issue.title[:50]}'"
        )

        from backend.ml.text_classifier import classify_issue_text, generate_smart_tags
        from backend.ml.similarity_engine import find_similar_issues
        from backend.models.issue import IssueCategory, IssueStatus, ChangeType, Comment, CommentType

        text_result = await classify_issue_text(
            title=issue.title,
            description=issue.description
        )

        similarity_result = await find_similar_issues(
            title=issue.title,
            description=issue.description,
            lat=issue.location_lat,
            lng=issue.location_lng,
            category=text_result.get("category", issue.category.value),
            db=db,
            exclude_uuid=str(issue.uuid)
        )

        if similarity_result.get("is_duplicate_detected", False):
            await self._handle_duplicate(issue, similarity_result, db, system_user_id)
            return

        changes_applied = []

        if text_result.get("category_confidence", 0) > 0.80 and issue.category.value == "other":
            old_category = issue.category.value
            try:
                issue.category = IssueCategory(text_result["category"])
                changes_applied.append(f"category: {old_category} → {text_result['category']}")
            except ValueError:
                pass

        issue.ai_suggested_category = text_result.get("category", issue.category.value)
        issue.ai_category_confidence = text_result.get("category_confidence", 0.0)
        issue.ai_tags = generate_smart_tags(
            issue.title, issue.description,
            issue.category.value, issue.location_city or ""
        )

        department = self.DEPARTMENT_ROUTING.get(
            issue.category.value,
            "General Services Department"
        )
        if not issue.assigned_department:
            issue.assigned_department = department
            changes_applied.append(f"routed to: {department}")

        issue.status = IssueStatus.UNDER_REVIEW
        changes_applied.append("status: reported → under_review")

        issue.ai_processed = True
        issue.ai_processed_at = datetime.utcnow()
        issue.similarity_score = similarity_result.get("highest_similarity", 0.0)

        self.create_history_entry(
            db=db,
            issue_id=issue.id,
            system_user_id=system_user_id,
            change_type=ChangeType.AI_UPDATE,
            old_value="reported",
            new_value="under_review",
            note=(
                f"Reporter Agent processed this issue. "
                f"Changes: {', '.join(changes_applied) if changes_applied else 'none'}. "
                f"Routed to: {department}."
            )
        )

        comment = Comment(
            issue_id=issue.id,
            user_id=system_user_id,
            content=(
                f"🤖 This issue has been automatically processed. "
                f"It has been routed to {department} and is now under review. "
                f"AI Confidence: {text_result.get('category_confidence', 0):.0%}"
            ),
            comment_type=CommentType.SYSTEM_MESSAGE,
            is_pinned=False
        )
        db.add(comment)
        issue.comment_count += 1

        try:
            from backend.utils.email import send_issue_status_update_email
            from backend.models.user import User

            reporter = db.execute(
                select(User).where(User.id == issue.reported_by)
            ).scalar_one_or_none()

            if reporter and reporter.email:
                await send_issue_status_update_email(
                    to_email=reporter.email,
                    user_name=reporter.name,
                    issue_title=issue.title,
                    issue_uuid=str(issue.uuid),
                    old_status="reported",
                    new_status="under_review",
                    status_note=f"Your issue has been received and routed to {department}."
                )
        except Exception as email_error:
            self.record_error(f"Email failed: {email_error}", str(issue.uuid))

        db.commit()

        self.record_action(
            f"Processed issue '{issue.title[:40]}'",
            {
                "issue_uuid": str(issue.uuid),
                "category": issue.category.value,
                "department": department,
                "changes": changes_applied,
                "similarity_score": similarity_result.get("highest_similarity", 0.0)
            }
        )

    async def _handle_duplicate(
        self,
        issue,
        similarity_result: dict,
        db,
        system_user_id: int
    ):
        """Handle a detected duplicate issue."""
        from backend.models.issue import IssueStatus, ChangeType, Comment, CommentType

        similar_issues = similarity_result.get("similar_issues", [])
        most_similar = similar_issues[0] if similar_issues else {}
        similarity_score = most_similar.get("overall_similarity", similarity_result.get("highest_similarity", 0.85))

        self.logger.info(
            f"Duplicate detected: {issue.uuid} similar to {most_similar.get('uuid', 'unknown')} "
            f"score={similarity_score:.2f}"
        )

        issue.status = IssueStatus.DUPLICATE
        issue.ai_processed = True
        issue.ai_processed_at = datetime.utcnow()
        issue.similarity_score = similarity_score

        comment = Comment(
            issue_id=issue.id,
            user_id=system_user_id,
            content=(
                f"🤖 This issue appears to be similar to an existing report "
                f"(similarity: {similarity_score:.0%}). "
                f"Please check the existing report for updates. "
                f"If this is a different issue, please contact support."
            ),
            comment_type=CommentType.SYSTEM_MESSAGE,
            is_pinned=True
        )
        db.add(comment)

        self.create_history_entry(
            db=db,
            issue_id=issue.id,
            system_user_id=system_user_id,
            change_type=ChangeType.AI_UPDATE,
            old_value="reported",
            new_value="duplicate",
            note=f"AI detected {similarity_score:.0%} similarity with existing issue"
        )

        try:
            from backend.utils.email import send_issue_status_update_email
            from backend.models.user import User

            reporter = db.execute(
                select(User).where(User.id == issue.reported_by)
            ).scalar_one_or_none()

            if reporter and reporter.email:
                await send_issue_status_update_email(
                    to_email=reporter.email,
                    user_name=reporter.name,
                    issue_title=issue.title,
                    issue_uuid=str(issue.uuid),
                    old_status="reported",
                    new_status="duplicate",
                    status_note=(
                        "Our AI detected that this issue is similar to an existing report in your area. "
                        "Please check the platform for the existing issue."
                    )
                )
        except Exception as e:
            self.record_error(f"Duplicate email failed: {e}", str(issue.uuid))

        db.commit()

        self.record_action(
            f"Marked as duplicate: '{issue.title[:40]}'",
            {
                "issue_uuid": str(issue.uuid),
                "similar_to": most_similar.get("uuid"),
                "similarity_score": similarity_score
            }
        )
