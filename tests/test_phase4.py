"""Unit and integration tests for Phase 3 features."""

import pytest
import asyncio
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from backend.main import app
from backend.database import Base, get_db
from backend.models.user import User, UserRole
from backend.models.issue import Issue, IssueCategory, IssueStatus, IssuePriority
from backend.models.volunteer import VolunteerTask, TaskStatus
from backend.agents.orchestrator import orchestrator
from backend.agents.resolver_agent import ResolverAgent
from backend.routes.websockets import ws_manager, broadcast_event


from backend.utils.auth import hash_password

SQLALCHEMY_DATABASE_URL = "sqlite:///./test_phase4.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Create test user and volunteer
    citizen = User(email="citizen@test.com", name="Test Citizen", role=UserRole.CITIZEN, password_hash=hash_password("pass123"))
    volunteer = User(email="volunteer@test.com", name="Test Volunteer", role=UserRole.VOLUNTEER, password_hash=hash_password("pass123"))

    db.add(citizen)
    db.add(volunteer)
    db.commit()

    yield
    db.close()
    Base.metadata.drop_all(bind=engine)


def test_resolver_volunteer_matching():
    db = TestingSessionLocal()
    resolver = ResolverAgent()

    # Create dummy issue
    issue = Issue(
        title="Pothole repair on 5th Ave",
        description="Large pothole near main crossroad.",
        category=IssueCategory.INFRASTRUCTURE,
        priority=IssuePriority.HIGH,
        location_lat=12.9716,
        location_lng=77.5946,
        reporter_id=1
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    matches = resolver.match_volunteers(
        issue_id=issue.id,
        lat=12.9716,
        lng=77.5946,
        category="infrastructure",
        db=db
    )

    assert isinstance(matches, list)
    assert len(matches) >= 1
    assert matches[0]["email"] == "volunteer@test.com"


def test_multi_agent_orchestration():
    db = TestingSessionLocal()

    issue = Issue(
        title="Broken street light at Night St",
        description="Dark street light bulb blown out creating hazard",
        category=IssueCategory.UTILITIES,
        priority=IssuePriority.MEDIUM,
        location_lat=12.9716,
        location_lng=77.5946,
        reporter_id=1
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)

    result = orchestrator.process_issue_workflow(
        issue_id=issue.id,
        db=db,
        auto_assign_volunteer=True
    )

    assert result["status"] == "completed"
    assert "resolution_plan" in result
    assert "assigned_department" in result["resolution_plan"]


def test_websocket_broadcast():
    client = TestClient(app)

    # Test WebSocket connection
    with client.websocket_connect("/ws/live") as websocket:
        data = websocket.receive_json()
        assert data["event"] == "connected"

        # Send ping heartbeat
        websocket.send_json({"type": "ping"})
        pong = websocket.receive_json()
        assert pong["type"] == "pong"
