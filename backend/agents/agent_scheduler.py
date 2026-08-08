"""Centralized Agent Scheduler for Smart Community Platform.

Manages background scheduling of all 5 autonomous agents:
- ReporterAgent: Every 5 minutes
- ResolverAgent: Every 6 hours
- AnalystAgent: Every Sunday at 2am
- VolunteerCoordinatorAgent: Every 1 hour
- CommunityAgent: On-demand (not scheduled)
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger

from backend.config import settings

logger = logging.getLogger("agents.scheduler")


class AgentScheduler:
    """Singleton scheduler for autonomous AI agents."""

    _instance: Optional["AgentScheduler"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.scheduler = AsyncIOScheduler()
        self.agents: dict = {}
        self._initialized = True
        logger.info("AgentScheduler initialized")

    def initialize(self):
        """Instantiate agents and register scheduled jobs."""
        from backend.agents.reporter_agent import ReporterAgent
        from backend.agents.resolver_agent import ResolverAgent
        from backend.agents.analyst_agent import AnalystAgent
        from backend.agents.volunteer_agent import VolunteerCoordinatorAgent
        from backend.agents.community_agent import CommunityAgent

        self.agents["reporter"] = ReporterAgent()
        self.agents["resolver"] = ResolverAgent()
        self.agents["analyst"] = AnalystAgent()
        self.agents["volunteer_coordinator"] = VolunteerCoordinatorAgent()
        self.agents["community"] = CommunityAgent()

        self.scheduler.add_job(
            func=self.agents["reporter"].run,
            trigger=IntervalTrigger(minutes=settings.AGENT_REPORTER_INTERVAL_MINUTES),
            id="agent_reporter",
            name="Reporter Agent (Intake Coordinator)",
            replace_existing=True,
            max_instances=1
        )

        self.scheduler.add_job(
            func=self.agents["resolver"].run,
            trigger=IntervalTrigger(hours=settings.AGENT_RESOLVER_INTERVAL_HOURS),
            id="agent_resolver",
            name="Resolver Agent (Case Manager)",
            replace_existing=True,
            max_instances=1
        )

        self.scheduler.add_job(
            func=self.agents["analyst"].run,
            trigger=CronTrigger(
                day_of_week=settings.AGENT_ANALYST_DAY_OF_WEEK,
                hour=settings.AGENT_ANALYST_HOUR,
                minute=0
            ),
            id="agent_analyst",
            name="Analyst Agent (Data Scientist)",
            replace_existing=True,
            max_instances=1
        )

        self.scheduler.add_job(
            func=self.agents["volunteer_coordinator"].run,
            trigger=IntervalTrigger(hours=settings.AGENT_VOLUNTEER_INTERVAL_HOURS),
            id="agent_volunteer_coordinator",
            name="Volunteer Coordinator Agent (HR Manager)",
            replace_existing=True,
            max_instances=1
        )

        logger.info("All 5 AI agents registered with APScheduler")

    def start(self):
        """Start background scheduler thread."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("APScheduler started successfully")

    def shutdown(self):
        """Gracefully shut down background scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            logger.info("APScheduler shut down")

    async def trigger_now(self, agent_name: str) -> dict:
        """Trigger an agent run immediately out-of-band."""
        key = str(agent_name).lower().strip().replace(" ", "_").replace("-", "_")
        if key.endswith("_agent"):
            key = key[:-6]
        
        alias_map = {
            "intake_coordinator": "reporter",
            "intake": "reporter",
            "case_manager": "resolver",
            "case": "resolver",
            "data_scientist": "analyst",
            "hr_manager": "volunteer_coordinator",
            "volunteer": "volunteer_coordinator",
            "volunteer_agent": "volunteer_coordinator",
            "citizen_assistant": "community",
            "rag": "community",
        }
        
        target_key = alias_map.get(key, key)
        if target_key not in self.agents:
            raise ValueError(f"Unknown agent: '{agent_name}'. Available agents: {list(self.agents.keys())}")

        agent = self.agents[target_key]
        logger.info(f"Manual trigger requested for agent: {target_key}")
        result = await agent.run()
        return result

    def get_status(self) -> dict:
        """Get status of scheduler and all registered jobs."""
        jobs_info = []

        if self.scheduler.running:
            for job in self.scheduler.get_jobs():
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
                jobs_info.append({
                    "id": job.id,
                    "name": job.name,
                    "next_run_at": next_run,
                    "trigger": str(job.trigger)
                })

        agent_definitions = [
            {
                "name": "reporter",
                "display_name": "Reporter Agent",
                "role": "Intake Coordinator",
                "schedule": f"Every {settings.AGENT_REPORTER_INTERVAL_MINUTES} minutes",
                "description": "Auto-triages new issues, runs duplicate check, routes to departments"
            },
            {
                "name": "resolver",
                "display_name": "Resolver Agent",
                "role": "Case Manager",
                "schedule": f"Every {settings.AGENT_RESOLVER_INTERVAL_HOURS} hours",
                "description": "Manages overdue escalations, sends reminders, auto-closes stale cases"
            },
            {
                "name": "analyst",
                "display_name": "Analyst Agent",
                "role": "Data Scientist",
                "schedule": f"Every Sunday at {settings.AGENT_ANALYST_HOUR}:00 AM",
                "description": "Weekly stats, trend detection, hotspot forecasting, priority model retraining"
            },
            {
                "name": "volunteer_coordinator",
                "display_name": "Volunteer Coordinator Agent",
                "role": "HR Manager",
                "schedule": f"Every {settings.AGENT_VOLUNTEER_INTERVAL_HOURS} hour",
                "description": "Proximity/skill matching for high-priority issues, volunteer performance tracking"
            },
            {
                "name": "community",
                "display_name": "Community Agent",
                "role": "24/7 Citizen Assistant",
                "schedule": "On-demand (24/7 Chat)",
                "description": "RAG-powered Q&A, status checking, platform guidance, action suggestions"
            }
        ]

        from backend.ml.model_manager import model_manager
        chroma_info = model_manager.get_status().get("models", {}).get("chroma_db", {})
        chroma_status = chroma_info.get("status", "not_attempted")

        return {
            "scheduler_running": self.scheduler.running,
            "total_agents": len(self.agents),
            "active_jobs": jobs_info,
            "agents": agent_definitions,
            "chromadb_status": chroma_status,
            "chromadb_connected": chroma_status in ["loaded", "lightweight_mode"]
        }


# Global singleton instance
agent_scheduler = AgentScheduler()
