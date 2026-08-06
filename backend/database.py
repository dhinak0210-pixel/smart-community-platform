import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.exc import OperationalError
from backend.config import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATABASE_URL = settings.DATABASE_URL

try:
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,  # Automatically check & reconnect stale connections
    )
except Exception as e:
    logger.critical(f"Failed to create database engine: {e}")
    raise e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI Dependency for database session management."""
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        logger.error(f"Database session error: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def test_connection():
    """Utility function to test database connectivity gracefully."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
            logger.info("Successfully connected to PostgreSQL database.")
            return True
    except OperationalError as e:
        logger.error(f"Could not connect to PostgreSQL database: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected database error: {e}")
        return False
