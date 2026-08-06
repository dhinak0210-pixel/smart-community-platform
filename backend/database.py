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
    engine = create_engine(
        DATABASE_URL,
        pool_size=5,
        max_overflow=10,
        pool_timeout=30,
        pool_recycle=1800,
        pool_pre_ping=True,
        echo=settings.DEBUG,
    )
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

        Base.metadata.create_all(bind=engine)
        tables = list(Base.metadata.tables.keys())
        logger.info(f"Database initialized successfully. Tables present/created: {', '.join(tables)}")
    except Exception as e:
        logger.error(f"Failed to initialize database tables: {e}", exc_info=True)
