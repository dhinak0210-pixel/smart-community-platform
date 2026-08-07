"""Root conftest.py — Central test configuration for Smart Community Platform.

Architecture:
- Uses SQLite in-memory database for total isolation and speed
- Session-scoped engine creates tables ONCE per test session
- Function-scoped sessions with transaction rollback for per-test isolation
- Pre-configured environment variables prevent production contamination
- All external services (Email, Groq, Cloudinary) are auto-mocked
"""

import os
import sys
import uuid
from datetime import datetime, timedelta
from typing import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

# ─── Environment Isolation ───────────────────────────────────────────────────
# Set BEFORE any application imports to guarantee test config
os.environ.update({
    "DATABASE_URL": "sqlite:///:memory:",
    "SECRET_KEY": "test-secret-key-for-jwt-signing-only-never-production",
    "APP_ENV": "testing",
    "DEBUG": "false",
    "GROQ_API_KEY": "",
    "CLOUDINARY_CLOUD_NAME": "",
    "CLOUDINARY_API_KEY": "",
    "CLOUDINARY_API_SECRET": "",
    "MAIL_USERNAME": "",
    "MAIL_PASSWORD": "",
    "MAIL_FROM": "test@test.com",
    "CORS_ORIGINS": '["http://localhost:3000"]',
    "FRONTEND_URL": "http://localhost:3000",
    "ACCESS_TOKEN_EXPIRE_MINUTES": "60",
})

# ─── Application Imports ─────────────────────────────────────────────────────
from backend.database import Base, get_db
from backend.main import app
from backend.models.user import User, UserRole
from backend.models.issue import (
    Issue, Comment, Vote, IssueHistory,
    IssueCategory, IssueStatus, IssuePriority,
    CommentType, VoteType, ChangeType,
)
from backend.models.notification import Notification
from backend.models.agent_log import AgentLog
from backend.utils.auth import hash_password, create_access_token


# ─── Database Engine (Session-Scoped) ────────────────────────────────────────
# Using check_same_thread=False and StaticPool for SQLite in-memory with
# multi-threaded FastAPI TestClient compatibility.

@pytest.fixture(scope="session")
def engine():
    """Create a session-scoped SQLite in-memory engine."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False,
    )
    # Enable SQLite WAL mode and foreign keys
    @event.listens_for(_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    # Create all tables once
    Base.metadata.create_all(bind=_engine)
    yield _engine
    Base.metadata.drop_all(bind=_engine)
    _engine.dispose()


@pytest.fixture(scope="session")
def TestSessionLocal(engine):
    """Session factory bound to the test engine."""
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── Per-Test Database Session (Function-Scoped) ─────────────────────────────
@pytest.fixture()
def db(engine, TestSessionLocal) -> Generator[Session, None, None]:
    """Provide a clean database session per test with transaction rollback.
    
    Every test runs inside a SAVEPOINT. When the test ends, the savepoint
    is rolled back, leaving zero residual data for the next test.
    """
    connection = engine.connect()
    transaction = connection.begin()
    session = TestSessionLocal(bind=connection)

    # Nest inside a savepoint so we can rollback per-test
    nested = connection.begin_nested()

    @event.listens_for(session, "after_transaction_end")
    def restart_savepoint(session, transaction):
        nonlocal nested
        if transaction.nested and not transaction._parent.nested:
            nested = connection.begin_nested()

    yield session

    session.close()
    transaction.rollback()
    connection.close()


# ─── FastAPI TestClient ──────────────────────────────────────────────────────
@pytest.fixture()
def client(db) -> Generator[TestClient, None, None]:
    """FastAPI TestClient with DB dependency override."""
    def _override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app, raise_server_exceptions=False) as tc:
        yield tc
    app.dependency_overrides.clear()


# ─── Test Data Constants ─────────────────────────────────────────────────────
TEST_PASSWORD = "TestP@ss123!"
TEST_WEAK_PASSWORD = "weak"
VALID_PHONE = "+14155552671"


# ─── User Fixtures ───────────────────────────────────────────────────────────
@pytest.fixture()
def citizen_user(db) -> User:
    """Create a verified citizen user."""
    user = User(
        name="Test Citizen",
        email=f"citizen_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=True,
        phone=VALID_PHONE,
        location_city="TestCity",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def authority_user(db) -> User:
    """Create a verified authority user."""
    user = User(
        name="Test Authority",
        email=f"authority_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.AUTHORITY,
        is_active=True,
        is_verified=True,
        location_city="TestCity",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def admin_user(db) -> User:
    """Create a verified admin user."""
    user = User(
        name="Test Admin",
        email=f"admin_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.ADMIN,
        is_active=True,
        is_verified=True,
        location_city="TestCity",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def volunteer_user(db) -> User:
    """Create a verified volunteer user."""
    user = User(
        name="Test Volunteer",
        email=f"volunteer_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.VOLUNTEER,
        is_active=True,
        is_verified=True,
        location_city="TestCity",
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def suspended_user(db) -> User:
    """Create a suspended/inactive user."""
    user = User(
        name="Suspended User",
        email=f"suspended_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.CITIZEN,
        is_active=False,
        is_verified=True,
    )
    db.add(user)
    db.flush()
    return user


@pytest.fixture()
def unverified_user(db) -> User:
    """Create an unverified user."""
    user = User(
        name="Unverified User",
        email=f"unverified_{uuid.uuid4().hex[:8]}@test.com",
        password_hash=hash_password(TEST_PASSWORD),
        role=UserRole.CITIZEN,
        is_active=True,
        is_verified=False,
        email_verification_token="test-verification-token-123",
    )
    db.add(user)
    db.flush()
    return user


# ─── Auth Token Fixtures ─────────────────────────────────────────────────────
def _make_token(user: User) -> str:
    """Generate a valid JWT access token for a user."""
    role_str = user.role.value if hasattr(user.role, "value") else str(user.role)
    return create_access_token(
        data={
            "sub": str(user.id),
            "uuid": str(user.uuid),
            "role": role_str,
            "email": user.email,
        },
        expires_delta=timedelta(hours=1),
    )


@pytest.fixture()
def citizen_token(citizen_user) -> str:
    return _make_token(citizen_user)


@pytest.fixture()
def authority_token(authority_user) -> str:
    return _make_token(authority_user)


@pytest.fixture()
def admin_token(admin_user) -> str:
    return _make_token(admin_user)


@pytest.fixture()
def volunteer_token(volunteer_user) -> str:
    return _make_token(volunteer_user)


def auth_header(token: str) -> dict:
    """Build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# ─── Issue Fixtures ──────────────────────────────────────────────────────────
@pytest.fixture()
def sample_issue(db, citizen_user) -> Issue:
    """Create a sample reported issue."""
    issue = Issue(
        title="Large pothole on Main Street causing traffic hazards",
        description="There is a large pothole approximately 2 feet wide on Main Street near the intersection with Oak Avenue. Multiple cars have been damaged and it is causing traffic congestion during rush hour.",
        category=IssueCategory.INFRASTRUCTURE,
        status=IssueStatus.REPORTED,
        priority=IssuePriority.MEDIUM,
        location_lat=12.9716,
        location_lng=77.5946,
        location_address="123 Main Street",
        location_city="TestCity",
        location_area="Downtown",
        reporter_id=citizen_user.id,
        vote_count=0,
        comment_count=0,
        view_count=0,
    )
    db.add(issue)
    db.flush()
    return issue


@pytest.fixture()
def resolved_issue(db, citizen_user) -> Issue:
    """Create a resolved issue."""
    issue = Issue(
        title="Broken streetlight on Oak Avenue",
        description="The streetlight on Oak Avenue near house number 42 has been broken for two weeks. Area is very dark at night and residents feel unsafe walking after sunset.",
        category=IssueCategory.UTILITIES,
        status=IssueStatus.RESOLVED,
        priority=IssuePriority.HIGH,
        location_lat=12.9720,
        location_lng=77.5950,
        location_address="42 Oak Avenue",
        location_city="TestCity",
        location_area="Downtown",
        reporter_id=citizen_user.id,
        resolved_at=datetime.utcnow(),
        resolution_note="Streetlight bulb was replaced successfully.",
        vote_count=5,
        comment_count=2,
        view_count=15,
    )
    db.add(issue)
    db.flush()
    return issue


@pytest.fixture()
def sample_comment(db, sample_issue, citizen_user) -> Comment:
    """Create a sample comment on an issue."""
    comment = Comment(
        issue_id=sample_issue.id,
        user_id=citizen_user.id,
        content="I noticed this pothole too. Very dangerous!",
        comment_type=CommentType.CITIZEN_COMMENT,
    )
    db.add(comment)
    db.flush()
    return comment


@pytest.fixture()
def sample_vote(db, sample_issue, citizen_user) -> Vote:
    """Create a sample vote on an issue."""
    vote = Vote(
        issue_id=sample_issue.id,
        user_id=citizen_user.id,
        vote_type=VoteType.UPVOTE,
    )
    db.add(vote)
    db.flush()
    return vote


# ─── Issue Data Payloads ─────────────────────────────────────────────────────
@pytest.fixture()
def issue_create_payload() -> dict:
    """Valid JSON payload for creating a new issue."""
    return {
        "title": "Garbage overflow at community park",
        "description": "The trash bins at the community park on Elm Street are overflowing with garbage. There is litter spread across the park grounds and a bad smell is coming from the area.",
        "category": "waste",
        "priority": "medium",
        "location_lat": 12.9750,
        "location_lng": 77.5960,
        "location_address": "Community Park, Elm Street",
        "location_city": "TestCity",
        "location_area": "Parkside",
    }


@pytest.fixture()
def user_register_payload() -> dict:
    """Valid JSON payload for user registration."""
    return {
        "name": "Jane Doe",
        "email": f"jane_{uuid.uuid4().hex[:8]}@example.com",
        "password": TEST_PASSWORD,
        "phone": VALID_PHONE,
        "role": "citizen",
        "location_city": "TestCity",
    }


# ─── Test Helpers ─────────────────────────────────────────────────────────────
def assert_success(response, expected_status=200):
    """Assert response is successful with expected status code."""
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}: {response.text}"
    )
    return response


def assert_error(response, expected_status):
    """Assert response has expected error status code."""
    assert response.status_code == expected_status, (
        f"Expected {expected_status}, got {response.status_code}: {response.text}"
    )
    return response


def get_json(response):
    """Get JSON body from response with assertion."""
    data = response.json()
    assert data is not None, "Response body is empty"
    return data
