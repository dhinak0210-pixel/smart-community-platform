"""Smoke test script for verifying all 5 autonomous AI agents and AgentScheduler."""

import asyncio
import sys
import logging
from sqlalchemy import select, func

from backend.database import SessionLocal, init_db
from backend.models.agent_log import AgentLog
from backend.agents.agent_scheduler import agent_scheduler
from backend.agents.community_agent import CommunityAgent

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("smoke_test")


async def main():
    logger.info("--- Starting Autonomous AI Agents Smoke Test ---")

    # 1. Initialize DB tables
    try:
        init_db()
        logger.info("✅ Database tables initialized successfully")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database tables: {e}")
        sys.exit(1)

    # 2. Initialize AgentScheduler
    try:
        agent_scheduler.initialize()
        status_info = agent_scheduler.get_status()
        logger.info(f"✅ AgentScheduler initialized. Registered agents: {len(status_info['agents'])}")
        assert len(status_info['agents']) == 5, "Expected 5 registered agents"
    except Exception as e:
        logger.error(f"❌ AgentScheduler initialization failed: {e}")
        sys.exit(1)

    # 3. Test Reporter Agent
    logger.info("\n--- Testing Reporter Agent ---")
    try:
        reporter_res = await agent_scheduler.trigger_now("reporter")
        logger.info(f"✅ Reporter Agent output: {reporter_res}")
        assert reporter_res["status"] in ["completed", "partial"], "Reporter status invalid"
    except Exception as e:
        logger.error(f"❌ Reporter Agent run failed: {e}")
        sys.exit(1)

    # 4. Test Resolver Agent
    logger.info("\n--- Testing Resolver Agent ---")
    try:
        resolver_res = await agent_scheduler.trigger_now("resolver")
        logger.info(f"✅ Resolver Agent output: {resolver_res}")
        assert resolver_res["status"] in ["completed", "partial"], "Resolver status invalid"
    except Exception as e:
        logger.error(f"❌ Resolver Agent run failed: {e}")
        sys.exit(1)

    # 5. Test Analyst Agent
    logger.info("\n--- Testing Analyst Agent ---")
    try:
        analyst_res = await agent_scheduler.trigger_now("analyst")
        logger.info(f"✅ Analyst Agent output: {analyst_res}")
        assert analyst_res["status"] in ["completed", "partial"], "Analyst status invalid"
    except Exception as e:
        logger.error(f"❌ Analyst Agent run failed: {e}")
        sys.exit(1)

    # 6. Test Volunteer Coordinator Agent
    logger.info("\n--- Testing Volunteer Coordinator Agent ---")
    try:
        vol_res = await agent_scheduler.trigger_now("volunteer_coordinator")
        logger.info(f"✅ Volunteer Coordinator Agent output: {vol_res}")
        assert vol_res["status"] in ["completed", "partial"], "Volunteer Coordinator status invalid"
    except Exception as e:
        logger.error(f"❌ Volunteer Coordinator Agent run failed: {e}")
        sys.exit(1)

    # 7. Test Community Agent (Citizen Q&A RAG)
    logger.info("\n--- Testing Community Agent (24/7 Citizen Q&A) ---")
    try:
        community_agent = CommunityAgent()
        db = SessionLocal()
        qa_res = await community_agent.answer_question(
            question="How do I report a broken street light in my area?",
            user_id=None,
            db=db
        )
        db.close()
        logger.info(f"✅ Community Agent Answer: {qa_res['answer'][:100]}...")
        assert "answer" in qa_res and len(qa_res["answer"]) > 10, "Community Agent answer invalid"
    except Exception as e:
        logger.error(f"❌ Community Agent run failed: {e}")
        sys.exit(1)

    # 8. Verify AgentLog Database Audit Trail
    logger.info("\n--- Verifying AgentLog Database Audit Trail ---")
    db = SessionLocal()
    try:
        total_logs = db.execute(select(func.count(AgentLog.id))).scalar() or 0
        logger.info(f"✅ Total AgentLog entries in database: {total_logs}")
        assert total_logs >= 4, f"Expected at least 4 AgentLog entries, found {total_logs}"

        latest_logs = db.execute(select(AgentLog).order_by(AgentLog.id.desc()).limit(5)).scalars().all()
        for log in latest_logs:
            logger.info(f"  • Log #{log.id}: agent={log.agent_name} status={log.status} actions={log.actions_taken}")
    finally:
        db.close()

    logger.info("\n🎉 --- ALL 5 AI AGENTS PASSED SMOKE TEST SUCCESSFULLY --- 🎉")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
