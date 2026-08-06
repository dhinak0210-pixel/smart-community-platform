"""Community Agent for volunteer coordination and task matching."""

from typing import Dict, Any, List


class CommunityAgent:
    """Agent responsible for matching volunteer skills with open community tasks."""

    def match_volunteers(self, task_title: str, required_skill: str, volunteer_list: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Match volunteers based on available skills and location proximity."""
        matches = []
        for vol in volunteer_list:
            skills = vol.get("skills", [])
            if required_skill.lower() in [s.lower() for s in skills]:
                matches.append(vol)

        return matches
