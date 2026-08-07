#!/usr/bin/env python3
"""
Database migration script for Smart Community Platform.
Runs Alembic migrations safely with error handling.
Call this before starting the application.
"""

import subprocess
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_migrations():
    """Run all pending database migrations."""
    logger.info("Starting database migrations...")
    logger.info("Checking current migration status...")

    # Step 1: Show current migration status
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            capture_output=True, text=True, check=True
        )
        logger.info(f"Current revision: {result.stdout.strip()}")
    except Exception as e:
        logger.warning(f"Could not get current revision: {e}")

    # Step 2: Run upgrade to head
    logger.info("Running: alembic upgrade head")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            capture_output=True, text=True, check=True,
            cwd=str(Path(__file__).parent.parent)
        )
        logger.info("Migration output:")
        if result.stdout:
            logger.info(result.stdout)
        logger.info("✅ Database migrations completed successfully")

    except subprocess.CalledProcessError as e:
        logger.error("❌ Migration FAILED!")
        logger.error(f"STDOUT: {e.stdout}")
        logger.error(f"STDERR: {e.stderr}")
        logger.error("Application will NOT start until migrations succeed")
        sys.exit(1)

    # Step 3: Verify migration succeeded
    try:
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "current"],
            capture_output=True, text=True, check=True
        )
        logger.info(f"New revision: {result.stdout.strip()}")
    except Exception as e:
        logger.warning(f"Could not verify migration: {e}")

    logger.info("Migration process complete. Starting application...")


if __name__ == "__main__":
    run_migrations()
