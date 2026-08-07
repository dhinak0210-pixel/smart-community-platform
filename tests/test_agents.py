"""Automated unit tests for AI Agent workflows."""

from backend.agents import ReporterAgent, ResolverAgent, AnalystAgent, CommunityAgent


def test_reporter_agent():
    """Test ReporterAgent priority scoring and keyword detection."""
    agent = ReporterAgent()
    analysis = agent.analyze_report(
        title="Emergency Water Pipe Burst",
        description="Hazardous flooding on main street causing severe traffic danger.",
        category="water_supply"
    )
    assert analysis["recommended_priority"] in ["urgent", "high", "critical", "medium", "low"]
    assert "detected_keywords" in analysis and isinstance(analysis["detected_keywords"], list)
    assert len(analysis["detected_keywords"]) >= 1


def test_resolver_agent():
    """Test ResolverAgent resolution plan generation."""
    agent = ResolverAgent()
    plan = agent.generate_resolution_plan(issue_id=42, title="Deep Pothole", category="pothole")
    assert plan["issue_id"] == 42
    assert len(plan["resolution_steps"]) >= 3


def test_analyst_agent():
    """Test AnalystAgent civic report compiling."""
    agent = AnalystAgent()
    report = agent.compile_civic_report(total_issues=10, resolved_count=9, top_category="street_light")
    assert report["civic_health_status"] == "Excellent"
    assert report["resolution_rate_percent"] == 90.0


def test_community_agent():
    """Test CommunityAgent volunteer matching."""
    agent = CommunityAgent()
    volunteers = [
        {"id": 1, "name": "Alice", "skills": ["Electrical", "First Aid"]},
        {"id": 2, "name": "Bob", "skills": ["Pavement", "Gardening"]},
    ]
    res = agent.match_volunteers("Repair Light", "Electrical", volunteers)
    matched = res["matched_volunteers"]
    assert len(matched) >= 1
    assert matched[0]["name"] == "Alice"
