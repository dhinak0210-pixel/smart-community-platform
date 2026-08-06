"""Image upload utility with Cloudinary cloud storage & local fallback."""

import os
import uuid
import logging
from typing import Optional
from fastapi import UploadFile, HTTPException, status
from PIL import Image
import cloudinary
import cloudinary.uploader

from backend.config import settings

logger = logging.getLogger(__name__)

# Configure Cloudinary if credentials are provided in settings
if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024  # 5 MB limit


async def save_upload_file(file: UploadFile) -> str:
    """Validate and upload an issue photo to Cloudinary or local storage.

    Returns the public image URL.
    """
    # 1. Extension check
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid file extension '{ext}'. Allowed extensions: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # 2. Read bytes & check size
    contents = await file.read()
    if len(contents) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds 5MB limit."
        )

    # 3. Validate image using Pillow
    try:
        file.file.seek(0)
        img = Image.open(file.file)
        img.verify()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Corrupt or invalid image file: {e}"
        )

    # Reset file pointer
    file.file.seek(0)

    # 4. Upload to Cloudinary if configured
    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        try:
            upload_result = cloudinary.uploader.upload(
                file.file,
                folder="smart_community_issues",
                resource_type="image"
            )
            return upload_result.get("secure_url")
        except Exception as e:
            logger.error(f"Cloudinary upload failed, falling back to local storage: {e}")

    # 5. Local storage fallback
    os.makedirs("uploads", exist_ok=True)
    unique_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join("uploads", unique_filename)

    with open(file_path, "wb") as buffer:
        buffer.write(contents)

    return f"/uploads/{unique_filename}"
