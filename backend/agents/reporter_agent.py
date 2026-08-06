"""Reporter Agent for automated issue ingestion and priority scoring."""

import logging
from typing import Dict, Any
from backend.config import settings

logger = logging.getLogger(__name__)


class ReporterAgent:
    """Agent responsible for analyzing incoming issue reports and assigning severity scores."""

    def __init__(self, groq_api_key: str = None):
        self.api_key = groq_api_key or settings.GROQ_API_KEY

    def analyze_report(self, title: str, description: str, category: str) -> Dict[str, Any]:
        """Analyze issue report text and recommend priority level and urgency keywords."""
        urgent_keywords = ["danger", "hazard", "overflow", "accident", "broken", "emergency", "fire", "flood"]
        text_lower = f"{title} {description}".lower()

        matched = [kw for kw in urgent_keywords if kw in text_lower]

        if len(matched) >= 2 or "emergency" in text_lower:
            recommended_priority = "urgent"
        elif len(matched) == 1:
            recommended_priority = "high"
        else:
            recommended_priority = "medium"

        return {
            "title": title,
            "category": category,
            "recommended_priority": recommended_priority,
            "detected_keywords": matched,
            "action_summary": f"Issue flagged with priority '{recommended_priority}'. Suggested for municipal dispatch."
        }
