"""Analyst Agent for trend analysis and civic insight reports."""

from typing import Dict, Any, List


class AnalystAgent:
    """Agent responsible for compiling trend summaries and civic health reports."""

    def compile_civic_report(self, total_issues: int, resolved_count: int, top_category: str) -> Dict[str, Any]:
        """Compile executive summary report of community issues."""
        rate = round((resolved_count / total_issues * 100), 1) if total_issues > 0 else 0.0

        if rate >= 80.0:
            health_status = "Excellent"
        elif rate >= 50.0:
            health_status = "Moderate"
        else:
            health_status = "Needs Attention"

        return {
            "civic_health_status": health_status,
            "resolution_rate_percent": rate,
            "primary_concern_category": top_category,
            "key_recommendation": f"Allocate additional resources to '{top_category}' repairs to improve resolution speed."
        }
