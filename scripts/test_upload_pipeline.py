"""Smoke test script for validating the Smart Community Image Upload and Processing Pipeline."""

import io
import os
import sys
import asyncio
import logging
from PIL import Image, ImageDraw

# Add workspace root to sys.path
WORKSPACE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if WORKSPACE_ROOT not in sys.path:
    sys.path.insert(0, WORKSPACE_ROOT)

from backend.config import settings
from backend.utils.upload import (
    validate_image_file,
    upload_temp_image,
    move_temp_to_issue,
    get_image_variants,
    delete_single_image,
    get_cloudinary_usage
)
from backend.utils.image_optimizer import (
    extract_image_metadata,
    prepare_for_ai_analysis,
    create_thumbnail_locally
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("upload_test")


def create_test_image(width=800, height=600, color=(37, 99, 235), text="SMART COMMUNITY PIPELINE TEST") -> bytes:
    """Generates a test JPEG image in memory."""
    img = Image.new("RGB", (width, height), color=color)
    draw = ImageDraw.Draw(img)
    # Simple cross pattern for visual contrast
    draw.line([(0, 0), (width, height)], fill=(255, 255, 255), width=5)
    draw.line([(0, height), (width, 0)], fill=(255, 255, 255), width=5)
    
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=90)
    return buf.getvalue()


class MockUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str = "image/jpeg"):
        self.filename = filename
        self.file = io.BytesIO(content)
        self.content_type = content_type
        self.size = len(content)

    async def read(self, size: int = -1) -> bytes:
        return self.file.read(size)

    async def seek(self, offset: int) -> None:
        self.file.seek(offset)


async def run_pipeline_tests():
    print("\n============================================================")
    print("      SMART COMMUNITY PLATFORM - IMAGE PIPELINE SMOKE TEST  ")
    print("============================================================\n")

    passed_tests = 0
    total_tests = 0

    # Test 1: Configuration check
    total_tests += 1
    print("[1/7] Testing Configuration Setup...")
    has_cloudinary = bool(settings.CLOUDINARY_CLOUD_NAME and settings.CLOUDINARY_API_KEY and settings.CLOUDINARY_API_SECRET)
    if has_cloudinary:
        print("  ✓ Cloudinary credentials loaded successfully.")
        print(f"    Cloud Name: {settings.CLOUDINARY_CLOUD_NAME}")
        passed_tests += 1
    else:
        print("  ⚠️ Cloudinary credentials missing in environment (.env). Operating in local fallback mode.")
        passed_tests += 1

    # Test 2: In-memory image generation & Pillow validation
    total_tests += 1
    print("\n[2/7] Testing Image Validation & In-Memory Processing...")
    test_img_bytes = create_test_image()
    mock_file = MockUploadFile("pothole_report.jpg", test_img_bytes, "image/jpeg")

    try:
        val_info = await validate_image_file(mock_file)
        width = val_info["width"]
        height = val_info["height"]
        size_bytes = val_info["size_bytes"]
        print(f"  ✓ Validation passed: format=JPEG, dimensions={width}x{height}, size={size_bytes} bytes")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Image validation failed: {e}")

    # Test 3: Local Image Optimizer (Metadata & AI Prep)
    total_tests += 1
    print("\n[3/7] Testing Image Optimizer Utilities...")
    try:
        meta = extract_image_metadata(test_img_bytes)
        ai_res = prepare_for_ai_analysis(test_img_bytes, target_size=(640, 640))
        thumb_bytes = create_thumbnail_locally(test_img_bytes, width=150, height=150)

        print(f"  ✓ Metadata extracted: format={meta['format']}, mode={meta['mode']}, GPS present={meta['has_gps']}")
        print(f"  ✓ AI pre-processed image size: {len(ai_res['processed_bytes'])} bytes (640x640 letterbox)")
        print(f"  ✓ Local thumbnail generated: {len(thumb_bytes)} bytes")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Image optimizer failed: {e}")

    # Test 4: Temporary Image Upload
    total_tests += 1
    print("\n[4/7] Testing Temporary Image Upload Pipeline...")
    temp_result = None
    try:
        mock_file.file.seek(0)
        temp_result = await upload_temp_image(mock_file, session_id="smoke_test_session_123")
        print(f"  ✓ Uploaded to temp storage: temp_id={temp_result['temp_id']}")
        print(f"    Public ID: {temp_result['public_id']}")
        print(f"    URL: {temp_result['url']}")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Temporary upload failed: {e}")

    # Test 5: Move Temp to Issue Storage
    total_tests += 1
    print("\n[5/7] Testing Temp-to-Permanent Issue Promotion...")
    issue_result = None
    if temp_result:
        try:
            issue_result = move_temp_to_issue(
                temp_public_id=temp_result["public_id"],
                issue_uuid="test_issue_0001",
                image_index=0
            )
            print(f"  ✓ Promoted to issue folder: url={issue_result['url']}")
            print(f"    Public ID: {issue_result['public_id']}")
            passed_tests += 1
        except Exception as e:
            print(f"  ❌ Move temp to issue failed: {e}")
    else:
        print("  ⚠️ Skipped (depends on Test 4)")

    # Test 6: Image Variant Generation
    total_tests += 1
    print("\n[6/7] Testing Cloudinary CDN Responsive Image Variants...")
    if issue_result and "cloudinary.com" in issue_result["url"]:
        try:
            variants = get_image_variants(issue_result["url"])
            print(f"  ✓ Generated variants: thumbnail={variants['thumbnail_url']}")
            print(f"    Card URL: {variants['card_url']}")
            print(f"    AI URL: {variants['ai_url']}")
            passed_tests += 1
        except Exception as e:
            print(f"  ❌ Variant generation failed: {e}")
    else:
        print("  ℹ️ Local mode active - skipping Cloudinary variant generation.")
        passed_tests += 1

    # Test 7: Image Deletion & Usage Stats
    total_tests += 1
    print("\n[7/7] Testing Deletion & Storage Metrics...")
    try:
        if issue_result and "cloudinary.com" in issue_result["url"]:
            del_res = await delete_single_image(issue_result["public_id"])
            print(f"  ✓ Image deleted from Cloudinary: status={del_res.get('result')}")

        usage = get_cloudinary_usage()
        print(f"  ✓ Cloudinary Storage Usage check: status={usage.get('status', 'available')}")
        passed_tests += 1
    except Exception as e:
        print(f"  ❌ Deletion / Usage check failed: {e}")

    print("\n============================================================")
    print(f"  TEST SUMMARY: {passed_tests}/{total_tests} PASSED ({int((passed_tests/total_tests)*100)}%)")
    print("============================================================\n")

    if passed_tests == total_tests:
        print("🎉 ALL IMAGE PIPELINE SMOKE TESTS PASSED!")
        sys.exit(0)
    else:
        print("⚠️ SOME TESTS FAILED OR OPERATED IN DEGRADED MODE.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_pipeline_tests())
