"""Smart Community Platform - Community Agent (24/7 Citizen Service)."""

import logging
from typing import Dict, Any, List, Optional

from backend.config import settings
from backend.agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)


class CommunityAgent(BaseAgent):
    """The 24/7 Customer Service Agent.
    
    NOT scheduled. Called on-demand from API.
    
    Capabilities:
    1. Answer citizen questions about their issues
    2. Provide issue status summaries
    3. Explain platform features
    4. Suggest similar issues to vote on
    5. Provide community statistics
    6. Guide citizens through reporting process
    """

    agent_name = "community"
    agent_description = "24/7 citizen assistance using RAG and LLM"

    PLATFORM_KNOWLEDGE = """
    Smart Community Platform is a civic-tech tool that:
    - Allows citizens to report local problems with photos and location
    - Shows all issues on an interactive map
    - Lets citizens vote on issues they care about
    - Connects citizens with local authorities
    - Tracks issue resolution progress
    - Matches volunteers to help with issues
    
    Issue statuses:
    - Reported: Just submitted, being reviewed
    - Under Review: Authority is looking at it
    - Acknowledged: Authority confirmed the issue
    - In Progress: Being actively worked on
    - Pending Citizen: Authority says it's fixed, waiting for your confirmation
    - Resolved: Issue has been fixed and confirmed
    - Rejected: Not a valid issue
    
    To report an issue: Click the blue "Report Issue" button, fill the form, drop a pin on the map.
    To vote: Click the heart icon on any issue card.
    To track your issues: Go to your profile and check "My Issues" tab.
    """

    def __init__(self, groq_api_key: str = None):
        super().__init__()
        self.api_key = groq_api_key or settings.GROQ_API_KEY

    def match_volunteers(
        self,
        task_title: str,
        required_skill: str,
        volunteer_list: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Match volunteers based on available skills, availability, and location proximity."""
        matches = []
        req_skill_clean = required_skill.lower()

        for vol in volunteer_list:
            skills = [s.lower() for s in vol.get("skills", [])]
            name = vol.get("name", "Volunteer")
            email = vol.get("email", "")
            vol_id = vol.get("id")
            reputation = vol.get("reputation_score", 0)

            matched_skills = [s for s in skills if req_skill_clean in s or s in req_skill_clean]
            if matched_skills or "general" in skills or not required_skill:
                match_score = 90.0 if matched_skills else 70.0
                if reputation >= 100:
                    match_score += 10.0

                matches.append({
                    "volunteer_id": vol_id,
                    "name": name,
                    "email": email,
                    "match_score": min(100.0, match_score),
                    "matched_skills": matched_skills or ["general assistance"],
                })

        matches.sort(key=lambda x: x["match_score"], reverse=True)

        return {
            "task_title": task_title,
            "required_skill": required_skill,
            "total_candidates_evaluated": len(volunteer_list),
            "matched_volunteers": matches,
            "agent": "CommunityAgent",
        }

    async def answer_question(
        self,
        question: str,
        user_id: Optional[int],
        db
    ) -> dict:
        """Main method to answer a citizen question."""
        self.logger.info(f"Community Agent answering: '{question[:60]}...'")

        relevant_issues = []
        try:
            from backend.ml.similarity_engine import semantic_search_issues
            relevant_issues = await semantic_search_issues(query=question, limit=5)
        except Exception as e:
            self.logger.warning(f"Semantic search failed in CommunityAgent: {e}")

        stats = {}
        try:
            from backend.utils.issue_helpers import get_issue_statistics
            stats = get_issue_statistics(db)
        except Exception as e:
            self.logger.warning(f"Failed to fetch issue stats: {e}")

        intent = self._detect_question_intent(question)

        answer = None
        if intent == "status_check":
            answer = await self._answer_status_question(question, user_id, db)
        elif intent == "how_to":
            answer = await self._answer_howto_question(question)
        elif intent == "statistics":
            answer = await self._answer_stats_question(stats, question)
        else:
            try:
                from backend.ml.groq_llm import answer_citizen_question
                answer = await answer_citizen_question(
                    question=question,
                    relevant_issues=relevant_issues,
                    platform_stats=stats
                )
            except Exception as e:
                self.logger.warning(f"Groq citizen answer failed: {e}")

        actions = self._suggest_actions(intent, question)

        sources = [
            f"Issue: {i.get('metadata', {}).get('uuid', '')[:8]}..."
            for i in relevant_issues[:3]
            if i.get("similarity", 0) > 0.5
        ]

        confidence = "high" if len(relevant_issues) > 3 else "medium" if answer else "low"

        self.record_action(
            f"Answered question: '{question[:40]}'",
            {
                "intent": intent,
                "relevant_issues_found": len(relevant_issues),
                "confidence": confidence
            }
        )

        return {
            "answer": answer or self._fallback_answer(question),
            "confidence": confidence,
            "relevant_issues": [
                {
                    "uuid": i.get("metadata", {}).get("uuid"),
                    "similarity": round(i.get("similarity", 0), 2)
                }
                for i in relevant_issues[:3]
                if i.get("similarity", 0) > 0.4
            ],
            "suggested_actions": actions,
            "sources": sources
        }

    def _detect_question_intent(self, question: str) -> str:
        """Classify what the citizen is asking about."""
        q_lower = question.lower()

        STATUS_KEYWORDS = [
            "status", "my issue", "what happened", "update",
            "resolved", "fixed", "when", "progress"
        ]
        HOWTO_KEYWORDS = [
            "how to", "how do", "how can", "report",
            "submit", "vote", "follow", "track"
        ]
        STATS_KEYWORDS = [
            "how many", "total", "statistics", "count",
            "most common", "popular", "area", "city"
        ]

        if any(kw in q_lower for kw in STATUS_KEYWORDS):
            return "status_check"
        elif any(kw in q_lower for kw in HOWTO_KEYWORDS):
            return "how_to"
        elif any(kw in q_lower for kw in STATS_KEYWORDS):
            return "statistics"
        else:
            return "general"

    async def _answer_status_question(
        self,
        question: str,
        user_id: Optional[int],
        db
    ) -> str:
        """Answer questions about issue status."""
        if not user_id:
            return (
                "To check your issue status, please log in to your account and go to your profile → My Issues. "
                "You can see the current status of all your reported issues there."
            )

        from backend.models.issue import Issue
        from sqlalchemy import select, and_

        recent_issues = db.execute(
            select(Issue)
            .where(
                and_(
                    Issue.reported_by == user_id,
                    Issue.deleted_at.is_(None)
                )
            )
            .order_by(Issue.created_at.desc())
            .limit(3)
        ).scalars().all()

        if not recent_issues:
            return "You have not reported any issues yet. Use the Report Issue button to report a community problem."

        status_summary = [
            f"'{issue.title[:40]}' → {issue.status.value.replace('_', ' ').title() if hasattr(issue.status, 'value') else str(issue.status).replace('_', ' ').title()}"
            for issue in recent_issues
        ]

        return (
            f"Here are your recent issues: {'; '.join(status_summary)}. "
            f"Click on any issue to see full details and updates."
        )

    async def _answer_howto_question(self, question: str) -> str:
        """Answer how-to questions using platform knowledge."""
        try:
            from backend.ml.groq_llm import call_groq

            prompt = f"""
            Answer this citizen's question about the Smart Community Platform.
            Be helpful, specific, and friendly. Keep it under 3 sentences.
            
            Platform Knowledge:
            {self.PLATFORM_KNOWLEDGE}
            
            Question: {question}
            
            Answer:
            """

            result = await call_groq(prompt, max_tokens=200, temperature=0.3)
            if result:
                return result
        except Exception:
            pass

        return self._fallback_answer(question)

    async def _answer_stats_question(
        self,
        stats: dict,
        question: str
    ) -> str:
        """Answer statistics questions."""
        return (
            f"Currently on Smart Community Platform: "
            f"There are {stats.get('total', 0)} total issues reported. "
            f"{stats.get('open', 0)} are still open and being worked on. "
            f"{stats.get('resolved', 0)} have been successfully resolved. "
            f"Our resolution rate is {stats.get('resolution_rate', 0):.1f}%."
        )

    def _suggest_actions(self, intent: str, question: str) -> List[str]:
        """Suggest relevant actions based on question intent."""
        actions = {
            "status_check": [
                "Go to your Profile → My Issues to see all your reports",
                "Click on any issue to see detailed status history",
                "You will receive an email when your issue status changes"
            ],
            "how_to": [
                "Click the blue 'Report Issue' button to get started",
                "Use the map to find existing issues in your area",
                "Vote on issues you care about to help prioritize them"
            ],
            "statistics": [
                "Visit the platform map to see all issues visually",
                "Filter issues by category or area using the sidebar"
            ],
            "general": [
                "Browse the map to see community issues near you",
                "Report any problem you see in your neighborhood",
                "Vote on issues that affect you to increase their priority"
            ]
        }
        return actions.get(intent, actions["general"])

    def _fallback_answer(self, question: str) -> str:
        """Rule-based fallback when LLM is unavailable."""
        q = question.lower()

        if "report" in q:
            return (
                "To report an issue, click the blue 'Report Issue' button, fill in the details, "
                "and drop a pin on the map to mark the location. You can also add a photo to help authorities."
            )
        if "status" in q or "my issue" in q:
            return (
                "To check your issue status, go to your Profile and click 'My Issues'. "
                "Each issue shows its current status and all history updates."
            )
        if "vote" in q:
            return (
                "To vote on an issue, click the heart icon on any issue card. "
                "More votes help prioritize issues for faster resolution."
            )
        if "volunteer" in q:
            return (
                "To become a volunteer, go to your Profile settings and register as a volunteer. "
                "You will receive notifications when your skills match nearby issues."
            )

        return (
            "Thank you for your question! Please browse the platform map or check the help section. "
            "For specific issues, go to your Profile → My Issues. To report a new problem, click the 'Report Issue' button."
        )

    async def execute(self, db) -> None:
        """Not used for scheduled runs (this agent is on-demand)."""
        pass
