"""Dedicated FastAPI router for image uploads, avatars, temp storage, and storage metrics."""

import uuid
import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.issue import Issue
from backend.utils.auth import get_current_user, require_role
from backend.utils.upload import (
    upload_temp_image,
    upload_user_avatar,
    delete_single_image,
    cleanup_temp_images,
    get_cloudinary_usage
)

router = APIRouter(prefix="", tags=["Image Upload"])
logger = logging.getLogger(__name__)


class ImageDeleteRequest(BaseModel):
    image_url: str


@router.post("/temp-image", status_code=status.HTTP_201_CREATED)
async def upload_temporary_image(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user)
):
    """Uploads an image to temporary storage prior to issue creation."""
    sess_id = session_id or f"{current_user.uuid}_{uuid.uuid4().hex[:8]}"
    result = await upload_temp_image(file, session_id=sess_id)

    return {
        "temp_id": result["temp_id"],
        "public_id": result["public_id"],
        "url": result["url"],
        "thumbnail_url": result["thumbnail_url"],
        "session_id": sess_id,
        "expires_in": "24 hours",
        "message": "Image uploaded. It will be attached when you submit your report."
    }


@router.post("/avatar", status_code=status.HTTP_200_OK)
async def upload_profile_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Uploads user profile avatar and updates database avatar_url."""
    res = await upload_user_avatar(file, user_uuid=str(current_user.uuid))
    
    current_user.avatar_url = res["url"]
    db.commit()
    db.refresh(current_user)

    logger.info(f"Avatar updated for user={current_user.uuid}")
    return {
        "avatar_url": res["url"],
        "thumbnail_url": res["thumbnail_url"],
        "message": "Profile photo updated successfully!"
    }


@router.delete("/avatar", status_code=status.HTTP_200_OK)
async def delete_profile_avatar(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Removes the profile avatar for the authenticated user."""
    if not current_user.avatar_url:
        return {"message": "No avatar to remove."}

    # Attempt to extract public_id if hosted on Cloudinary
    url = current_user.avatar_url
    if "cloudinary.com" in url:
        parts = url.split("/upload/")
        if len(parts) > 1:
            public_id = parts[1].split(".")[0]
            # Strip version string e.g. v12345/
            if "/" in public_id and public_id.startswith("v"):
                public_id = "/".join(public_id.split("/")[1:])
            await delete_single_image(public_id)

    current_user.avatar_url = None
    db.commit()
    db.refresh(current_user)

    return {"message": "Profile photo removed successfully."}


@router.delete("/issue/{issue_uuid}/image", status_code=status.HTTP_200_OK)
async def remove_issue_image(
    issue_uuid: str,
    payload: ImageDeleteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Removes a specific image from an issue (Reporter or Authority only)."""
    try:
        parsed_uuid = uuid.UUID(issue_uuid)
        issue = db.execute(select(Issue).where(Issue.uuid == parsed_uuid, Issue.deleted_at == None)).scalar_one_or_none()
    except ValueError:
        issue = None

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    # Check permission
    is_reporter = issue.reported_by_id == current_user.id
    is_authority = current_user.role in [UserRole.AUTHORITY, UserRole.ADMIN]
    if not (is_reporter or is_authority):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to modify images for this issue.")

    target_url = payload.image_url.strip()
    image_list = list(issue.image_urls or [])
    if target_url not in image_list and issue.image_url != target_url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Image URL is not associated with this issue.")

    # Extract public_id if Cloudinary URL
    if "cloudinary.com" in target_url:
        parts = target_url.split("/upload/")
        if len(parts) > 1:
            pid = parts[1].split(".")[0]
            if "/" in pid and pid.startswith("v"):
                pid = "/".join(pid.split("/")[1:])
            await delete_single_image(pid)

    if target_url in image_list:
        image_list.remove(target_url)

    issue.image_urls = image_list
    new_primary = image_list[0] if image_list else None
    issue.image_url = new_primary

    db.commit()
    db.refresh(issue)

    logger.info(f"Image removed from issue={issue_uuid}: target={target_url}")
    return {
        "message": "Image removed successfully.",
        "remaining_images": len(image_list),
        "new_primary_url": new_primary
    }


@router.get("/usage", status_code=status.HTTP_200_OK)
def fetch_storage_usage(
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Retrieves Cloudinary storage and bandwidth usage (Admin only)."""
    usage = get_cloudinary_usage()
    return usage


@router.post("/cleanup-temp", status_code=status.HTTP_200_OK)
async def trigger_temp_cleanup(
    older_than_hours: int = Query(24, ge=1, le=720),
    current_user: User = Depends(require_role(UserRole.ADMIN))
):
    """Triggers manual cleanup of expired temp images (Admin only)."""
    report = await cleanup_temp_images(older_than_hours=older_than_hours)
    return report
