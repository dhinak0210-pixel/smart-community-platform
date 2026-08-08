"""Production-grade image processing and Cloudinary cloud storage management module.

Handles image validation, client EXIF orientation correction, RGBA conversion,
Cloudinary CDN upload, variant generation, temp uploads, and cleanup tasks.
"""

import io
import os
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import aiofiles
from PIL import Image, ExifTags
from fastapi import UploadFile, HTTPException, status
import cloudinary
import cloudinary.uploader
import cloudinary.api
from cloudinary.utils import cloudinary_url

from backend.config import settings

logger = logging.getLogger(__name__)

# Configure Cloudinary credentials once at module level
if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
    cloudinary.config(
        cloud_name=settings.CLOUDINARY_CLOUD_NAME,
        api_key=settings.CLOUDINARY_API_KEY,
        api_secret=settings.CLOUDINARY_API_SECRET,
        secure=True,
    )

ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "webp"}
ALLOWED_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_BYTES = settings.MAX_IMAGE_SIZE_MB * 1024 * 1024
MAX_IMAGES_PER_ISSUE = settings.MAX_IMAGES_PER_ISSUE
CLOUDINARY_BASE_FOLDER = "smart-community"


def get_uploads_dir() -> str:
    """Return path to uploads directory with fallback to /tmp/uploads if permissions are restricted."""
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    dir_path = os.path.join(base_dir, "uploads")
    try:
        os.makedirs(dir_path, exist_ok=True)
        return dir_path
    except Exception:
        fallback = "/tmp/uploads"
        os.makedirs(fallback, exist_ok=True)
        return fallback



async def validate_image_file(
    file: UploadFile,
    max_size_mb: Optional[float] = None
) -> Dict[str, Any]:
    """Complete image validation pipeline checking type, size, dimensions & integrity.
    
    Returns:
        dict: Image metadata including width, height, format, size_bytes, size_mb, mode.
    Raises:
        HTTPException: 400 Bad Request with user-friendly error message.
    """
    limit_mb = max_size_mb or settings.MAX_IMAGE_SIZE_MB
    limit_bytes = int(limit_mb * 1024 * 1024)

    # Step 1: Filename check
    filename = file.filename or ""
    if not filename.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please select an image file to upload."
        )

    # Step 2: Check file extension
    ext = os.path.splitext(filename)[1].lstrip(".").lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{ext}' is not allowed. Please upload a JPG, PNG, or WEBP image."
        )

    # Step 3: Size check on initial chunk read
    chunk = await file.read(limit_bytes + 1)
    if len(chunk) > limit_bytes:
        approx_mb = round(len(chunk) / (1024 * 1024), 1)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image is too large. Maximum size is {limit_mb}MB. Your file is approximately {approx_mb}MB."
        )

    # Step 4 & 5: Reset pointer & read full content
    await file.seek(0)
    full_content = await file.read()
    await file.seek(0)

    # Step 6: Verify image header and type using Pillow
    try:
        img = Image.open(io.BytesIO(full_content))
    except Exception as e:
        logger.warning(f"Image validation failed for '{filename}': Pillow failed to open ({e})")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The file you uploaded is not a valid image. Please upload a real JPG, PNG, or WEBP photo."
        )

    # Step 7: Verify format
    img_format = (img.format or "").lower()
    if img_format not in {"jpeg", "jpg", "png", "webp"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Image format '{img.format}' is not supported. Please use JPG, PNG, or WEBP."
        )

    # Step 8: Dimension checks
    width, height = img.size
    if width < 50 or height < 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image is too small. Minimum size is 50x50 pixels. Please upload a larger photo."
        )
    if width > 20000 or height > 20000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image dimensions are too large. Maximum is 20000x20000 pixels."
        )

    # Step 9: Verify image integrity
    try:
        img.verify()
    except Exception as e:
        logger.warning(f"Corrupted image uploaded '{filename}': {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image file appears to be corrupted. Please try a different photo."
        )

    # Step 10: Reset pointer finally
    await file.seek(0)

    size_mb = round(len(full_content) / (1024 * 1024), 2)
    logger.debug(f"Image validated: {filename} ({width}x{height}, {size_mb}MB, {img_format})")

    return {
        "valid": True,
        "width": width,
        "height": height,
        "format": img_format,
        "size_bytes": len(full_content),
        "size_mb": size_mb,
        "mode": img.mode,
    }


def process_image_before_upload(
    image_bytes: bytes,
    max_width: int = 1920,
    max_height: int = 1080,
    fix_rotation: bool = True,
    convert_to: str = "JPEG"
) -> bytes:
    """Processes image in memory: corrects EXIF rotation, converts RGBA to RGB, downscales."""
    img = Image.open(io.BytesIO(image_bytes))

    # Step 2: Fix EXIF orientation
    if fix_rotation:
        try:
            exif = img._getexif()
            if exif is not None:
                for tag, value in exif.items():
                    if ExifTags.TAGS.get(tag) == "Orientation":
                        if value == 3:
                            img = img.rotate(180, expand=True)
                        elif value == 6:
                            img = img.rotate(270, expand=True)
                        elif value == 8:
                            img = img.rotate(90, expand=True)
                        break
        except (AttributeError, Exception):
            pass

    # Step 3: Handle mode and alpha channels
    if img.mode in ("RGBA", "LA", "P"):
        background = Image.new("RGB", img.size, (255, 255, 255))
        if img.mode == "P":
            img = img.convert("RGBA")
        background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
        img = background
    elif img.mode != "RGB":
        img = img.convert("RGB")

    # Step 4: Downscale if larger than maximum bounds while maintaining aspect ratio
    if img.width > max_width or img.height > max_height:
        img.thumbnail((max_width, max_height), Image.LANCZOS)

    # Step 5: Export optimized image bytes
    output = io.BytesIO()
    fmt = convert_to.upper()
    if fmt == "JPEG":
        img.save(output, format="JPEG", quality=85, optimize=True, progressive=True)
    elif fmt == "PNG":
        img.save(output, format="PNG", optimize=True)
    elif fmt == "WEBP":
        img.save(output, format="WEBP", quality=85, method=6)
    else:
        img.save(output, format="JPEG", quality=85, optimize=True)

    result_bytes = output.getvalue()
    logger.debug(
        f"Image processed: original_size={len(image_bytes)/1024:.1f}KB, "
        f"processed_size={len(result_bytes)/1024:.1f}KB, dims={img.width}x{img.height}"
    )
    return result_bytes


async def upload_issue_image(
    file: UploadFile,
    issue_uuid: str,
    image_index: int = 0,
    is_primary: bool = False
) -> Dict[str, Any]:
    """Uploads an issue photo to Cloudinary within structured folder hierarchy."""
    info = await validate_image_file(file)
    content = await file.read()
    await file.seek(0)

    processed_bytes = process_image_before_upload(
        content,
        max_width=1920,
        max_height=1080,
        fix_rotation=True
    )

    image_name = "primary" if (is_primary or image_index == 0) else f"img_{image_index:03d}"
    public_id = f"{CLOUDINARY_BASE_FOLDER}/issues/{issue_uuid}/{image_name}"

    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        try:
            result = cloudinary.uploader.upload(
                processed_bytes,
                public_id=public_id,
                overwrite=True,
                resource_type="image",
                transformation=[
                    {"quality": "auto:good"},
                    {"fetch_format": "auto"}
                ],
                tags=[f"issue:{issue_uuid}", "community-issue"],
                context={
                    "issue_uuid": issue_uuid,
                    "uploaded_at": datetime.utcnow().isoformat(),
                    "image_index": str(image_index)
                }
            )

            thumb_url, _ = cloudinary_url(
                result["public_id"],
                width=400, height=300,
                crop="fill", quality="auto",
                fetch_format="auto"
            )

            small_url, _ = cloudinary_url(
                result["public_id"],
                width=150, height=150,
                crop="fill", quality="auto",
                fetch_format="auto"
            )

            logger.info(f"Issue image uploaded to Cloudinary: issue={issue_uuid}, index={image_index}")
            return {
                "url": result["secure_url"],
                "public_id": result["public_id"],
                "width": result.get("width", info["width"]),
                "height": result.get("height", info["height"]),
                "format": result.get("format", info["format"]),
                "size_bytes": result.get("bytes", len(processed_bytes)),
                "thumbnail_url": thumb_url,
                "small_url": small_url,
            }
        except Exception as e:
            logger.warning(f"Cloudinary upload failed, falling back to local storage: {e}")

    # Local fallback storage if Cloudinary credentials are not present or upload failed
    uploads_dir = get_uploads_dir()
    filename = f"{issue_uuid}_{image_name}.jpg"
    filepath = os.path.join(uploads_dir, filename)
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(processed_bytes)

    local_url = f"/uploads/{filename}"
    return {
        "url": local_url,
        "public_id": filename,
        "width": info["width"],
        "height": info["height"],
        "format": "jpg",
        "size_bytes": len(processed_bytes),
        "thumbnail_url": local_url,
        "small_url": local_url,
    }


async def upload_user_avatar(
    file: UploadFile,
    user_uuid: str
) -> Dict[str, Any]:
    """Uploads user profile avatar with automatic face-centering crop."""
    info = await validate_image_file(file)
    content = await file.read()
    await file.seek(0)

    processed_bytes = process_image_before_upload(
        content,
        max_width=1000,
        max_height=1000,
        fix_rotation=True
    )

    public_id = f"{CLOUDINARY_BASE_FOLDER}/avatars/{user_uuid}"

    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        try:
            result = cloudinary.uploader.upload(
                processed_bytes,
                public_id=public_id,
                overwrite=True,
                resource_type="image",
                transformation=[
                    {
                        "width": 400, "height": 400,
                        "crop": "fill", "gravity": "face",
                        "quality": "auto", "fetch_format": "auto"
                    }
                ],
                tags=[f"user:{user_uuid}", "avatar"]
            )

            small_url, _ = cloudinary_url(
                public_id,
                width=80, height=80,
                crop="fill", gravity="face",
                quality="auto", fetch_format="auto"
            )

            logger.info(f"Avatar uploaded to Cloudinary for user={user_uuid}")
            return {
                "url": result["secure_url"],
                "thumbnail_url": small_url,
                "public_id": result["public_id"]
            }
        except Exception as e:
            logger.warning(f"Cloudinary avatar upload failed, falling back to local storage: {e}")

    # Local fallback
    uploads_dir = get_uploads_dir()
    filename = f"avatar_{user_uuid}.jpg"
    filepath = os.path.join(uploads_dir, filename)
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(processed_bytes)

    local_url = f"/uploads/{filename}"
    return {
        "url": local_url,
        "thumbnail_url": local_url,
        "public_id": filename
    }


async def delete_issue_images(issue_uuid: str) -> Dict[str, Any]:
    """Deletes all images under the Cloudinary folder associated with an issue."""
    folder = f"{CLOUDINARY_BASE_FOLDER}/issues/{issue_uuid}"
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        return {"deleted": 0, "errors": ["Cloudinary not configured"]}

    deleted_count = 0
    errors: List[str] = []

    try:
        resources = cloudinary.api.resources(
            type="upload",
            prefix=folder,
            max_results=20
        )
    except Exception as e:
        logger.warning(f"Could not list Cloudinary resources for folder '{folder}': {e}")
        return {"deleted": 0, "errors": [str(e)]}

    for resource in resources.get("resources", []):
        pid = resource.get("public_id")
        try:
            res = cloudinary.uploader.destroy(pid)
            if res.get("result") == "ok":
                deleted_count += 1
            else:
                errors.append(f"Destroy returned {res.get('result')} for {pid}")
        except Exception as err:
            errors.append(str(err))
            logger.warning(f"Failed to delete resource '{pid}': {err}")

    try:
        cloudinary.api.delete_folder(folder)
    except Exception:
        pass

    logger.info(f"Issue images deleted for issue={issue_uuid}: deleted={deleted_count}, errors={len(errors)}")
    return {"deleted": deleted_count, "errors": errors}


async def delete_single_image(public_id: str) -> bool:
    """Deletes one specific image asset from Cloudinary storage by public ID."""
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        return False
    try:
        result = cloudinary.uploader.destroy(public_id)
        success = result.get("result") == "ok"
        if success:
            logger.info(f"Image deleted from Cloudinary: {public_id}")
        else:
            logger.warning(f"Image deletion returned non-ok status: {result}")
        return success
    except Exception as e:
        logger.error(f"Failed to delete Cloudinary image '{public_id}': {e}")
        return False


def get_image_variants(
    public_id: str,
    include_blur_placeholder: bool = False
) -> Dict[str, str]:
    """Generates transformed dynamic CDN URLs for various image sizes."""
    if not settings.CLOUDINARY_CLOUD_NAME:
        url = f"/uploads/{public_id}"
        return {
            "original": url,
            "large": url,
            "medium": url,
            "thumbnail": url,
            "small": url,
            "blur_placeholder": url
        }

    large_url, _ = cloudinary_url(public_id, width=1200, quality="auto:good", fetch_format="auto")
    medium_url, _ = cloudinary_url(public_id, width=800, quality="auto:good", fetch_format="auto")
    thumb_url, _ = cloudinary_url(public_id, width=400, height=300, crop="fill", quality="auto", fetch_format="auto")
    small_url, _ = cloudinary_url(public_id, width=150, height=150, crop="fill", quality="auto", fetch_format="auto")
    orig_url, _ = cloudinary_url(public_id, quality="auto", fetch_format="auto")

    variants = {
        "original": orig_url,
        "large": large_url,
        "medium": medium_url,
        "thumbnail": thumb_url,
        "small": small_url,
    }

    if include_blur_placeholder:
        blur_url, _ = cloudinary_url(public_id, width=20, quality=1, effect="blur:2000", fetch_format="auto")
        variants["blur_placeholder"] = blur_url

    return variants


async def upload_temp_image(
    file: UploadFile,
    session_id: str
) -> Dict[str, Any]:
    """Uploads temporary image before issue creation. Stored in temp folder."""
    info = await validate_image_file(file)
    content = await file.read()
    await file.seek(0)

    processed_bytes = process_image_before_upload(
        content,
        max_width=1920,
        max_height=1080,
        fix_rotation=True
    )

    temp_id = f"temp_{session_id}_{uuid.uuid4().hex[:8]}"
    public_id = f"{CLOUDINARY_BASE_FOLDER}/temp/{temp_id}"

    if settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET:
        try:
            result = cloudinary.uploader.upload(
                processed_bytes,
                public_id=public_id,
                overwrite=False,
                tags=["temp", f"session:{session_id}", f"expires:{datetime.utcnow().date()}"],
                context={"temp": "true", "session_id": session_id}
            )

            thumb_url, _ = cloudinary_url(
                result["public_id"],
                width=400, height=300,
                crop="fill", quality="auto", fetch_format="auto"
            )

            return {
                "temp_id": temp_id,
                "public_id": result["public_id"],
                "url": result["secure_url"],
                "image_url": result["secure_url"],
                "thumbnail_url": thumb_url,
                "expires_in": "24 hours"
            }
        except Exception as e:
            logger.warning(f"Failed to upload temp image to Cloudinary, falling back to local storage: {e}")

    uploads_dir = get_uploads_dir()
    filename = f"{temp_id}.jpg"
    filepath = os.path.join(uploads_dir, filename)
    async with aiofiles.open(filepath, "wb") as f:
        await f.write(processed_bytes)

    local_url = f"/uploads/{filename}"
    return {
        "temp_id": temp_id,
        "public_id": filename,
        "url": local_url,
        "image_url": local_url,
        "thumbnail_url": local_url,
        "expires_in": "24 hours"
    }


def move_temp_to_issue(
    temp_public_id: str,
    issue_uuid: str,
    image_index: int = 0
) -> Dict[str, Any]:
    """Moves uploaded temporary image to permanent issue folder location in Cloudinary or local storage."""
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        filename = temp_public_id
        if filename.startswith("/uploads/"):
            filename = filename.replace("/uploads/", "")
        elif filename.startswith("uploads/"):
            filename = filename.replace("uploads/", "")

        if not filename.endswith((".jpg", ".jpeg", ".png", ".webp")):
            filename = f"{filename}.jpg"

        url = f"/uploads/{filename}"
        return {"url": url, "image_url": url, "public_id": filename, "thumbnail_url": url}

    image_name = "primary" if image_index == 0 else f"img_{image_index:03d}"
    new_public_id = f"{CLOUDINARY_BASE_FOLDER}/issues/{issue_uuid}/{image_name}"

    full_temp_public_id = temp_public_id
    if not full_temp_public_id.startswith(f"{CLOUDINARY_BASE_FOLDER}/temp/"):
        full_temp_public_id = f"{CLOUDINARY_BASE_FOLDER}/temp/{temp_public_id}"

    try:
        result = cloudinary.uploader.rename(
            full_temp_public_id,
            new_public_id,
            overwrite=True
        )
        cloudinary.uploader.add_tag(f"issue:{issue_uuid}", [new_public_id])
        cloudinary.uploader.remove_tag("temp", [new_public_id])

        variants = get_image_variants(new_public_id)
        final_url = result.get("secure_url", variants["original"])
        return {
            "url": final_url,
            "image_url": final_url,
            "public_id": new_public_id,
            "thumbnail_url": variants["thumbnail"]
        }
    except Exception as e:
        logger.error(f"Failed to move temp image '{full_temp_public_id}' to '{new_public_id}': {e}")
        variants = get_image_variants(full_temp_public_id)
        fallback_url = variants["original"]
        return {
            "url": fallback_url,
            "image_url": fallback_url,
            "public_id": full_temp_public_id,
            "thumbnail_url": variants["thumbnail"]
        }


async def cleanup_temp_images(older_than_hours: int = 24) -> Dict[str, Any]:
    """Deletes temporary images created over older_than_hours ago."""
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        return {"deleted_count": 0, "checked_count": 0, "older_than_hours": older_than_hours}

    try:
        resources = cloudinary.api.resources_by_tag("temp", max_results=500)
    except Exception as e:
        logger.warning(f"Cloudinary temp tag query failed: {e}")
        return {"deleted_count": 0, "error": str(e)}

    cutoff = datetime.utcnow() - timedelta(hours=older_than_hours)
    deleted = 0
    total_found = len(resources.get("resources", []))

    for r in resources.get("resources", []):
        created_str = r.get("created_at", "").replace("Z", "")
        try:
            created_at = datetime.fromisoformat(created_str)
            if created_at < cutoff:
                cloudinary.uploader.destroy(r["public_id"])
                deleted += 1
        except Exception as err:
            logger.warning(f"Cleanup failed for resource '{r.get('public_id')}': {err}")

    logger.info(f"Temp image cleanup finished: deleted={deleted}/{total_found}")
    return {
        "deleted_count": deleted,
        "checked_count": total_found,
        "older_than_hours": older_than_hours
    }


def get_cloudinary_usage() -> Dict[str, Any]:
    """Fetches Cloudinary storage and bandwidth usage metrics for administrative monitoring."""
    if not (settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET):
        return {"error": "Cloudinary credentials not configured."}

    try:
        usage = cloudinary.api.usage()
        storage = usage.get("storage", {})
        bandwidth = usage.get("bandwidth", {})
        
        storage_used = storage.get("usage", 0)
        storage_limit = storage.get("limit", 1)
        bw_used = bandwidth.get("usage", 0)
        bw_limit = bandwidth.get("limit", 1)

        return {
            "storage_used_mb": round(storage_used / (1024 * 1024), 2),
            "storage_limit_mb": round(storage_limit / (1024 * 1024), 2),
            "storage_percent": round((storage_used / storage_limit) * 100, 1) if storage_limit else 0.0,
            "bandwidth_used_mb": round(bw_used / (1024 * 1024), 2),
            "bandwidth_limit_mb": round(bw_limit / (1024 * 1024), 2),
            "bandwidth_percent": round((bw_used / bw_limit) * 100, 1) if bw_limit else 0.0,
            "total_images": usage.get("resources", 0),
            "transformations_used": usage.get("transformations", {}).get("usage", 0)
        }
    except Exception as e:
        logger.error(f"Failed to fetch Cloudinary usage: {e}")
        return {"error": "Could not fetch Cloudinary usage metrics."}


# Backwards compatibility helper functions & aliases
async def validate_image(file: UploadFile) -> None:
    """Legacy alias for validate_image_file."""
    await validate_image_file(file)


async def upload_image(file: UploadFile, folder: str = "smart_community_issues", public_id: Optional[str] = None) -> str:
    """Legacy helper for image upload returning single URL string."""
    info = await upload_issue_image(file, issue_uuid=public_id or uuid.uuid4().hex, is_primary=True)
    return info["url"]


async def save_upload_file(file: UploadFile) -> str:
    """Legacy alias for upload_image."""
    return await upload_image(file)


def delete_image(public_id: str) -> bool:
    """Legacy synchronous wrapper for single image deletion."""
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return cloudinary.uploader.destroy(public_id).get("result") == "ok"
        return loop.run_until_complete(delete_single_image(public_id))
    except Exception:
        return False


def get_optimized_url(public_id: str, width: int = 800, quality: str = "auto") -> str:
    """Legacy helper returning transformed URL."""
    variants = get_image_variants(public_id)
    return variants.get("medium", variants["original"])
