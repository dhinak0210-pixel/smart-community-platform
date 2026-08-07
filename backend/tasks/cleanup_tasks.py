"""Background scheduled cleanup tasks for temporary and orphaned image storage."""

import asyncio
import logging
from typing import Callable, Any
from datetime import datetime, timedelta
import cloudinary.api
import cloudinary.uploader
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.config import settings
from backend.utils.upload import cleanup_temp_images, CLOUDINARY_BASE_FOLDER
from backend.models.issue import Issue

logger = logging.getLogger(__name__)


async def run_temp_image_cleanup():
    """Background task running every 6 hours to remove abandoned temporary images."""
    logger.info("Background temp image cleanup task initialized.")
    while True:
        try:
            await asyncio.sleep(6 * 60 * 60)  # Wait 6 hours
            logger.info("Executing scheduled temp image cleanup...")
            result = await cleanup_temp_images(older_than_hours=24)
            logger.info(f"Scheduled temp image cleanup completed: {result}")
        except asyncio.CancelledError:
            logger.info("Temp image cleanup task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in temp image cleanup task: {e}")
            await asyncio.sleep(60)  # Wait 1 min before retrying loop on unexpected failure


async def run_orphaned_images_cleanup(db_session_factory: Callable[[], Session]):
    """Background task running every 24 hours to find and delete Cloudinary images without database records."""
    logger.info("Background orphaned image cleanup task initialized.")
    while True:
        try:
            await asyncio.sleep(24 * 60 * 60)  # Wait 24 hours
            if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
                continue

            logger.info("Starting orphaned Cloudinary images check...")
            prefix = f"{CLOUDINARY_BASE_FOLDER}/issues/"
            
            try:
                resources = cloudinary.api.resources(
                    type="upload",
                    prefix=prefix,
                    max_results=500
                )
            except Exception as req_err:
                logger.warning(f"Orphan cleanup failed listing Cloudinary resources: {req_err}")
                continue

            db: Session = db_session_factory()
            orphaned_count = 0

            try:
                for r in resources.get("resources", []):
                    public_id = r.get("public_id", "")
                    # Format: smart-community/issues/{issue_uuid}/primary or img_001
                    parts = public_id.split("/")
                    if len(parts) >= 3:
                        issue_uuid_str = parts[2]
                        try:
                            import uuid
                            parsed_uuid = uuid.UUID(issue_uuid_str)
                            issue_exists = db.execute(
                                select(Issue).where(Issue.uuid == parsed_uuid, Issue.deleted_at == None)
                            ).scalar_one_or_none()

                            if not issue_exists:
                                cloudinary.uploader.destroy(public_id)
                                orphaned_count += 1
                                logger.info(f"Deleted orphaned image: {public_id}")
                        except ValueError:
                            pass
            finally:
                db.close()

            logger.info(f"Orphaned image cleanup finished: removed {orphaned_count} orphaned images.")
        except asyncio.CancelledError:
            logger.info("Orphaned image cleanup task cancelled.")
            break
        except Exception as e:
            logger.error(f"Error in orphaned image cleanup task: {e}")
            await asyncio.sleep(60)
