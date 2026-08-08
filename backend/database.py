"""Database connection and session lifecycle management for Smart Community Platform.

This module initializes the SQLAlchemy 2.0 engine, configures connection pooling,
provides FastAPI database session dependencies, and defines health check / initialization helpers.
"""

import time
import logging
from typing import Generator, Dict, Any
from sqlalchemy import create_engine, text, event, Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session, DeclarativeBase
from sqlalchemy.exc import SQLAlchemyError, OperationalError, DatabaseError, IntegrityError

from backend.config import settings

# Setup logger for database operations
logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# 1. Custom Database Exceptions
# ------------------------------------------------------------------------------
class DatabaseConnectionError(Exception):
    """Raised when connecting to the database server fails."""
    pass


class DatabaseQueryError(Exception):
    """Raised when a database query execution fails."""
    pass


class DatabaseIntegrityError(Exception):
    """Raised when a database constraint violation occurs."""
    pass


# ------------------------------------------------------------------------------
# 2. Database Connection URL & SSL Formatting for Neon.tech
# ------------------------------------------------------------------------------
def _format_database_url(url: str) -> str:
    """Ensure sslmode=require is present in DATABASE_URL for Neon.tech compatibility."""
    if "neon.tech" in url and "sslmode=" not in url:
        separator = "&" if "?" in url else "?"
        url = f"{url}{separator}sslmode=require"
    return url


DATABASE_URL = _format_database_url(settings.DATABASE_URL)


def _mask_database_url(url: str) -> str:
    """Mask sensitive credentials in database URL for safe logging and status reporting."""
    try:
        if "@" in url:
            scheme_and_auth, host_path = url.split("@", 1)
            scheme = scheme_and_auth.split("://")[0]
            return f"{scheme}://***:***@{host_path}"
        return url
    except Exception:
        return "postgresql://***:***@***"


# ------------------------------------------------------------------------------
# 3. SQLAlchemy Engine Initialization & Connection Pooling
# ------------------------------------------------------------------------------
try:
    if DATABASE_URL.startswith("sqlite"):
        engine_kwargs = {
            "connect_args": {"check_same_thread": False},
            "pool_pre_ping": True,
            "echo": settings.DEBUG,
        }
    else:
        engine_kwargs = {
            "pool_size": 5,
            "max_overflow": 10,
            "pool_timeout": 30,
            "pool_recycle": 1800,
            "pool_pre_ping": True,
            "echo": settings.DEBUG,
        }
    engine = create_engine(DATABASE_URL, **engine_kwargs)
    logger.info(f"Database engine created successfully for {_mask_database_url(DATABASE_URL)}")
except Exception as e:
    logger.critical(f"Failed to initialize database engine: {e}", exc_info=True)
    raise DatabaseConnectionError(f"Engine creation failed: {e}") from e


# Add slow query warning logger (> 1.0 second execution time)
@event.listens_for(Engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    conn.info.setdefault("query_start_time", []).append(time.time())


@event.listens_for(Engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, execmany):
    total_time = time.time() - conn.info["query_start_time"].pop()
    if total_time > 1.0:
        logger.warning(f"Slow query detected ({total_time:.3f}s): {statement[:150]}...")


# ------------------------------------------------------------------------------
# 4. Session Factory & Base Class Definition
# ------------------------------------------------------------------------------
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    bind=engine,
)


class Base(DeclarativeBase):
    """Declarative Base class for all ORM models with helper methods."""

    def __repr__(self) -> str:
        """Return clear string representation showing model name and key attributes."""
        attrs = []
        for key in self.__table__.columns.keys():
            value = getattr(self, key, None)
            attrs.append(f"{key}={value!r}")
        return f"<{self.__class__.__name__}({', '.join(attrs)})>"

    def to_dict(self) -> Dict[str, Any]:
        """Convert ORM model instance into a Python dictionary."""
        return {
            column.name: getattr(self, column.name, None)
            for column in self.__table__.columns
        }


# ------------------------------------------------------------------------------
# 5. Database Dependency Injection Provider for FastAPI
# ------------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """FastAPI Dependency providing a transactional database session per request.

    Yields:
        Session: Active SQLAlchemy Session instance.
    """
    db = SessionLocal()
    try:
        yield db
    except IntegrityError as e:
        logger.error(f"Database integrity constraint error: {e}")
        db.rollback()
        raise DatabaseIntegrityError(f"Database constraint violation: {e.orig}") from e
    except OperationalError as e:
        logger.error(f"Database operational error during request: {e}")
        db.rollback()
        raise DatabaseConnectionError(f"Database connection error: {e.orig}") from e
    except SQLAlchemyError as e:
        logger.error(f"Database query error during request: {e}")
        db.rollback()
        raise DatabaseQueryError(f"Database query failed: {e}") from e
    except Exception as e:
        logger.error(f"Unexpected error during database session lifecycle: {e}")
        db.rollback()
        raise
    finally:
        db.close()


# ------------------------------------------------------------------------------
# 6. Database Health Check & Startup Initialization Helpers
# ------------------------------------------------------------------------------
def check_db_connection() -> bool:
    """Test database connectivity by executing a simple ping query.

    Returns:
        bool: True if connection is alive and query succeeds, False otherwise.
    """
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            logger.info("Database health check ping succeeded.")
            return True
    except OperationalError as e:
        logger.error(f"Database health check failed (OperationalError): {e}")
        return False
    except Exception as e:
        logger.error(f"Database health check failed (Unexpected): {e}")
        return False


def init_db() -> None:
    """Initialize database tables using Base.metadata.create_all on startup."""
    try:
        # Import all ORM models so Base knows about them before creation
        import backend.models  # noqa: F401
        from backend.models.issue import Issue, IssueCategory, IssueStatus, IssuePriority
        from backend.models.user import User, UserRole
        from backend.utils.auth import hash_password
        from datetime import datetime, timedelta
        import random

        Base.metadata.create_all(bind=engine)
        tables = list(Base.metadata.tables.keys())
        logger.info(f"Database initialized successfully. Tables present/created: {', '.join(tables)}")

        # Auto-seed Tamil Nadu demo issues if DB is empty or has < 5 issues
        db = SessionLocal()
        try:
            issue_count = db.query(Issue).count()
            if issue_count < 5:
                logger.info(f"Auto-seeding Tamil Nadu demo issues (current count: {issue_count})...")
                citizen = db.query(User).filter(User.role == UserRole.CITIZEN).first()
                if not citizen:
                    citizen = User(
                        name="Citizen TamilNadu",
                        email="citizen1@demo.com",
                        password_hash=hash_password("DemoPass123!"),
                        role=UserRole.CITIZEN,
                        is_active=True,
                        is_verified=True,
                        location_city="Chennai"
                    )
                    db.add(citizen)
                    db.commit()

                tn_demo_issues = [
                    {
                        "title": "Severe Pothole & Road Damage on Anna Salai (Mount Road)",
                        "description": "Deep road erosion and pothole near Mount Road Metro station causing severe traffic bottlenecks and safety risk for two-wheelers. Immediate repair required from Greater Chennai Corporation.",
                        "category": IssueCategory.INFRASTRUCTURE,
                        "status": IssueStatus.IN_PROGRESS,
                        "priority": IssuePriority.HIGH,
                        "lat": 13.0604, "lng": 80.2496, "city": "Chennai", "area": "Anna Salai", "address": "Anna Salai, Mount Road, Chennai"
                    },
                    {
                        "title": "Stormwater Drain Waterlogging in T. Nagar",
                        "description": "Monsoon rainwater accumulation on Usman Road near Ranganathan Street due to clogged stormwater drains. Pedestrians unable to cross shop fronts.",
                        "category": IssueCategory.FLOODING,
                        "status": IssueStatus.REPORTED,
                        "priority": IssuePriority.HIGH,
                        "lat": 13.0418, "lng": 80.2341, "city": "Chennai", "area": "T. Nagar", "address": "Usman Road, T. Nagar, Chennai"
                    },
                    {
                        "title": "Broken Streetlights on OMR IT Corridor (Kandanchavadi)",
                        "description": "All 12 streetlights from Kandanchavadi junction to Perungudi on Rajiv Gandhi Salai (OMR) are inactive after nightfall, creating unsafe conditions for night shift workers.",
                        "category": IssueCategory.UTILITIES,
                        "status": IssueStatus.ACKNOWLEDGED,
                        "priority": IssuePriority.MEDIUM,
                        "lat": 12.9642, "lng": 80.2471, "city": "Chennai", "area": "OMR Corridor", "address": "Kandanchavadi, OMR Road, Chennai"
                    },
                    {
                        "title": "Traffic Light Malfunction on Avinashi Road",
                        "description": "The automated traffic signal at Lakshmi Mills junction on Avinashi Road, Coimbatore is stuck on amber, causing chaotic traffic jams during peak morning hours.",
                        "category": IssueCategory.TRAFFIC,
                        "status": IssueStatus.ASSIGNED,
                        "priority": IssuePriority.CRITICAL,
                        "lat": 11.0168, "lng": 76.9558, "city": "Coimbatore", "area": "Peelamedu", "address": "Lakshmi Mills Junction, Avinashi Road, Coimbatore"
                    },
                    {
                        "title": "Garbage Dumping near Koyambedu Bus Terminus",
                        "description": "Huge accumulation of commercial organic waste dumped on the perimeter road near CMBT Koyambedu. Odor and stray animal safety concern.",
                        "category": IssueCategory.WASTE,
                        "status": IssueStatus.RESOLVED,
                        "priority": IssuePriority.MEDIUM,
                        "lat": 13.0694, "lng": 80.1948, "city": "Chennai", "area": "Koyambedu", "address": "CMBT Outer Ring Road, Koyambedu, Chennai"
                    },
                    {
                        "title": "Waste Dump near Meenakshi Amman Temple Perimeter",
                        "description": "Plastic and paper waste piling up along East Chitrai Street near Madurai Meenakshi Temple. Sanitation team needed for daily clearance.",
                        "category": IssueCategory.WASTE,
                        "status": IssueStatus.IN_PROGRESS,
                        "priority": IssuePriority.HIGH,
                        "lat": 9.9195, "lng": 78.1193, "city": "Madurai", "area": "Town Hall", "address": "East Chitrai Street, Madurai"
                    },
                    {
                        "title": "Open Canal & Damaged Footpath near Chathiram Bus Stand",
                        "description": "Concrete slab covering the drainage canal broke near Chathiram Bus Stand in Tiruchirappalli. High risk of pedestrian falls at night.",
                        "category": IssueCategory.SAFETY,
                        "status": IssueStatus.UNDER_REVIEW,
                        "priority": IssuePriority.CRITICAL,
                        "lat": 10.8272, "lng": 78.6946, "city": "Tiruchirappalli", "area": "Chathiram", "address": "Chathiram Bus Stand Rd, Trichy"
                    },
                    {
                        "title": "Fallen Tree Branch at Five Roads Junction",
                        "description": "A heavy banyan tree branch fell across Five Roads intersection in Salem following heavy thunderstorm winds, blocking one lane of vehicular traffic.",
                        "category": IssueCategory.ENVIRONMENT,
                        "status": IssueStatus.ACKNOWLEDGED,
                        "priority": IssuePriority.HIGH,
                        "lat": 11.6643, "lng": 78.1460, "city": "Salem", "area": "Five Roads", "address": "Five Roads Junction, Salem"
                    }
                ]

                for data in tn_demo_issues:
                    if not db.query(Issue).filter(Issue.title == data["title"]).first():
                        iss = Issue(
                            title=data["title"],
                            description=data["description"],
                            short_description=data["description"][:250],
                            category=data["category"],
                            status=data["status"],
                            priority=data["priority"],
                            location_lat=data["lat"],
                            location_lng=data["lng"],
                            location_address=data["address"],
                            location_city=data["city"],
                            location_area=data["area"],
                            reporter_id=citizen.id,
                            ai_processed=True,
                            vote_count=random.randint(15, 60),
                            comment_count=random.randint(2, 8),
                            view_count=random.randint(40, 300),
                            created_at=datetime.utcnow() - timedelta(days=random.randint(1, 10))
                        )
                        db.add(iss)
                db.commit()
                logger.info("✅ Auto-seeded Tamil Nadu demo issues successfully.")
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}", exc_info=True)
