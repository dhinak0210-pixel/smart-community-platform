"""Agent Tests — Resolver Agent.

Tests the ResolverAgent's deterministic heuristic resolution plan generation
and volunteer matching logic without Groq API calls.
"""

import pytest
from unittest.mock import patch, MagicMock

from backend.agents.resolver_agent import ResolverAgent


# ═══════════════════════════════════════════════════════════════════════════════
# Resolution Plan Generation Tests (Heuristic Fallback)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolverAgentHeuristic:
    """Test ResolverAgent.generate_resolution_plan() heuristic fallback."""

    def setup_method(self):
        self.agent = ResolverAgent(groq_api_key="")

    def test_infrastructure_plan(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=1,
            title="Large pothole on Main Street",
            category="infrastructure",
        )
        assert plan["assigned_department"] == "Department of Public Works"
        assert len(plan["resolution_steps"]) >= 3
        assert plan["estimated_completion_hours"] == 48
        assert plan["issue_id"] == 1

    def test_utility_plan(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=2,
            title="Broken street light",
            category="light utility",
        )
        assert "Electrical" in plan["assigned_department"] or "Utilities" in plan["assigned_department"]
        assert plan["estimated_completion_hours"] == 24

    def test_water_plan(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=3,
            title="Water pipe leak",
            category="water pipe flood",
        )
        assert "Water" in plan["assigned_department"]
        assert plan["estimated_completion_hours"] == 12

    def test_waste_plan(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=4,
            title="Garbage overflow",
            category="waste trash",
        )
        assert "Sanitation" in plan["assigned_department"]
        assert plan["estimated_completion_hours"] == 18

    def test_generic_plan(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=5,
            title="Something else",
            category="other",
        )
        assert "General" in plan["assigned_department"] or "Municipal" in plan["assigned_department"]
        assert plan["estimated_completion_hours"] == 36

    def test_plan_has_required_fields(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=99, title="Test", category="other"
        )
        assert "issue_id" in plan
        assert "title" in plan
        assert "category" in plan
        assert "assigned_department" in plan
        assert "resolution_steps" in plan
        assert "estimated_completion_hours" in plan
        assert "agent" in plan

    def test_agent_name_indicates_heuristic(self):
        plan = self.agent.generate_resolution_plan(
            issue_id=1, title="Test", category="other"
        )
        assert "Heuristic" in plan["agent"]

    def test_all_plans_have_field_inspection_step(self):
        """Every resolution plan should start with a field inspection."""
        for cat in ["infrastructure", "light", "water", "waste", "other"]:
            plan = self.agent.generate_resolution_plan(
                issue_id=1, title="Test", category=cat
            )
            first_step = plan["resolution_steps"][0].lower()
            assert "inspect" in first_step or "dispatch" in first_step


# ═══════════════════════════════════════════════════════════════════════════════
# Base Agent Properties Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestResolverAgentProperties:
    """Test resolver agent class properties."""

    def test_agent_name(self):
        agent = ResolverAgent(groq_api_key="")
        assert agent.agent_name == "resolver"

    def test_agent_description(self):
        agent = ResolverAgent(groq_api_key="")
        assert "lifecycle" in agent.agent_description.lower() or "escalation" in agent.agent_description.lower()

    def test_record_action_increments_counter(self):
        agent = ResolverAgent(groq_api_key="")
        assert agent.actions_taken == 0
        agent.record_action("test action")
        assert agent.actions_taken == 1
        agent.record_action("another action")
        assert agent.actions_taken == 2

    def test_record_error_appends_to_list(self):
        agent = ResolverAgent(groq_api_key="")
        assert len(agent.errors) == 0
        agent.record_error("something failed", "uuid-123")
        assert len(agent.errors) == 1
        assert "uuid-123" in agent.errors[0]
