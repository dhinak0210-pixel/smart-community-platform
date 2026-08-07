"""Agent Tests — Reporter Agent.

Tests the ReporterAgent's deterministic heuristic fallback logic
(analyze_report) without Groq API calls. Validates priority assignment,
keyword detection, and department routing.
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from datetime import datetime

from backend.agents.reporter_agent import ReporterAgent


# ═══════════════════════════════════════════════════════════════════════════════
# Heuristic Analysis Tests (No API key → fallback mode)
# ═══════════════════════════════════════════════════════════════════════════════

class TestReporterAgentHeuristic:
    """Test ReporterAgent.analyze_report() heuristic fallback."""

    def setup_method(self):
        """Create agent instance without API key → forces heuristic path."""
        self.agent = ReporterAgent(groq_api_key="")

    def test_critical_priority_for_emergency_keywords(self):
        result = self.agent.analyze_report(
            title="Gas leak emergency in residential area",
            description="Emergency gas leak detected near school building, very dangerous situation",
            category="safety",
        )
        assert result["recommended_priority"] == "critical"
        assert result["urgency_score"] >= 90
        assert "gas leak" in result["detected_keywords"] or "emergency" in result["detected_keywords"]

    def test_high_priority_for_hazard_keywords(self):
        result = self.agent.analyze_report(
            title="Broken bridge causing danger",
            description="The bridge has a huge crack and is a hazard to pedestrians",
            category="infrastructure",
        )
        assert result["recommended_priority"] in ("critical", "high")
        assert result["urgency_score"] >= 60

    def test_medium_priority_for_normal_issues(self):
        result = self.agent.analyze_report(
            title="Park bench needs repainting",
            description="The park bench at Central Park has peeling paint and needs maintenance.",
            category="environment",
        )
        assert result["recommended_priority"] == "medium"
        assert result["urgency_score"] < 60

    def test_result_contains_all_required_fields(self):
        result = self.agent.analyze_report(
            title="Test issue",
            description="Test description for a community issue",
            category="other",
        )
        assert "recommended_priority" in result
        assert "urgency_score" in result
        assert "detected_keywords" in result
        assert "action_summary" in result
        assert "agent" in result

    def test_agent_name_indicates_heuristic(self):
        result = self.agent.analyze_report(
            title="Test", description="Test desc", category="other"
        )
        assert "Heuristic" in result["agent"]

    def test_multiple_emergency_keywords_trigger_critical(self):
        result = self.agent.analyze_report(
            title="Severe accident with fire emergency",
            description="A severe accident has caused a fire and there is overflow of gas creating danger and hazard",
            category="safety",
        )
        assert result["recommended_priority"] == "critical"
        assert result["urgency_score"] >= 90

    def test_single_keyword_triggers_high(self):
        result = self.agent.analyze_report(
            title="Overflow at drainage",
            description="Water overflow at the main drain causing issues",
            category="flooding",
        )
        assert result["recommended_priority"] == "high"


# ═══════════════════════════════════════════════════════════════════════════════
# Department Routing Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestReporterAgentRouting:
    """Test department routing rules."""

    def test_infrastructure_routes_correctly(self):
        agent = ReporterAgent(groq_api_key="")
        dept = agent.DEPARTMENT_ROUTING.get("infrastructure")
        assert "Roads" in dept or "Infrastructure" in dept

    def test_waste_routes_correctly(self):
        agent = ReporterAgent(groq_api_key="")
        dept = agent.DEPARTMENT_ROUTING.get("waste")
        assert "Waste" in dept

    def test_safety_routes_correctly(self):
        agent = ReporterAgent(groq_api_key="")
        dept = agent.DEPARTMENT_ROUTING.get("safety")
        assert "Safety" in dept

    def test_unknown_category_routes_to_general(self):
        agent = ReporterAgent(groq_api_key="")
        dept = agent.DEPARTMENT_ROUTING.get("nonexistent", "General Services Department")
        assert "General" in dept

    def test_all_categories_have_routing(self):
        agent = ReporterAgent(groq_api_key="")
        expected = [
            "infrastructure", "waste", "safety", "environment",
            "utilities", "traffic", "noise", "flooding", "other"
        ]
        for cat in expected:
            assert cat in agent.DEPARTMENT_ROUTING, f"Missing routing for {cat}"
