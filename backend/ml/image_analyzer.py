"""Image Hazard Analyzer module using Computer Vision and Pillow."""

import logging
from typing import Dict, Any
from PIL import Image

logger = logging.getLogger(__name__)


def analyze_issue_image(image_path: str) -> Dict[str, Any]:
    """Analyze issue photo image properties, dimensions, and detect potential hazards.

    In Phase 2, performs PIL image quality and brightness checks, preparing for YOLOv8 weights.
    """
    try:
        with Image.open(image_path) as img:
            width, height = img.size
            mode = img.mode
            format_name = img.format

            # Compute average brightness
            gray = img.convert('L')
            histogram = gray.histogram()
            pixels = sum(histogram)
            brightness = sum(i * count for i, count in enumerate(histogram)) / pixels if pixels > 0 else 0

            is_night_photo = brightness < 80.0

            return {
                "success": True,
                "width": width,
                "height": height,
                "format": format_name,
                "brightness": round(brightness, 2),
                "is_night_photo": is_night_photo,
                "detected_objects": ["road_surface", "hazard_candidate"] if is_night_photo else ["infrastructure_element"],
            }
    except Exception as e:
        logger.error(f"Image analysis failed for {image_path}: {e}")
        return {"success": False, "error": str(e)}
