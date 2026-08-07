"""Image optimization and analysis preparation utilities.

Provides metadata extraction, local thumbnail creation, quality estimation,
watermarking, and letterboxed image preparation for AI/ML models.
"""

import io
import math
import logging
from typing import Dict, Any, Tuple, List, Optional
from PIL import Image, ImageFilter, ImageDraw, ImageFont, ExifTags

logger = logging.getLogger(__name__)


def extract_image_metadata(image_bytes: bytes) -> Dict[str, Any]:
    """Extracts safe image metadata including dimensions, camera info, aspect ratio, and dominant colors."""
    img = Image.open(io.BytesIO(image_bytes))
    width, height = img.size
    img_format = (img.format or "").upper()
    mode = img.mode

    camera_make: Optional[str] = None
    camera_model: Optional[str] = None
    taken_at: Optional[str] = None
    has_exif = False
    has_gps = False

    try:
        exif = img._getexif()
        if exif is not None:
            has_exif = True
            for tag, val in exif.items():
                tag_name = ExifTags.TAGS.get(tag)
                if tag_name == "Make" and isinstance(val, str):
                    camera_make = val.strip()
                elif tag_name == "Model" and isinstance(val, str):
                    camera_model = val.strip()
                elif tag_name in ("DateTimeOriginal", "DateTime") and isinstance(val, str):
                    taken_at = val.strip()
                elif tag_name == "GPSInfo":
                    has_gps = True
    except Exception as e:
        logger.debug(f"EXIF parsing skipped: {e}")

    # Calculate aspect ratio
    aspect = width / height if height > 0 else 1.0
    common_ratios = {
        "16:9": 16 / 9,
        "4:3": 4 / 3,
        "1:1": 1.0,
        "3:4": 3 / 4,
        "9:16": 9 / 16,
    }
    closest_ratio = min(common_ratios.keys(), key=lambda r: abs(common_ratios[r] - aspect))

    # Extract top 3 dominant colors
    dominant_colors: List[str] = []
    try:
        small_img = img.copy().convert("RGB")
        small_img.thumbnail((100, 100), Image.NEAREST)
        quantized = small_img.quantize(colors=5)
        palette = quantized.getpalette()
        if palette:
            color_counts = sorted(quantized.getcolors(maxcolors=10000) or [], key=lambda c: c[0], reverse=True)
            for _, color_idx in color_counts[:3]:
                r = palette[color_idx * 3]
                g = palette[color_idx * 3 + 1]
                b = palette[color_idx * 3 + 2]
                dominant_colors.append(f"#{r:02x}{g:02x}{b:02x}")
    except Exception as err:
        logger.debug(f"Dominant color extraction skipped: {err}")

    return {
        "width": width,
        "height": height,
        "format": img_format,
        "mode": mode,
        "has_exif": has_exif,
        "camera_make": camera_make,
        "camera_model": camera_model,
        "taken_at": taken_at,
        "has_gps": has_gps,
        "dominant_colors": dominant_colors,
        "is_portrait": height > width,
        "is_landscape": width > height,
        "aspect_ratio": closest_ratio,
    }


def create_thumbnail_locally(
    image_bytes: bytes,
    width: int = 300,
    height: int = 200
) -> bytes:
    """Generates a downscaled thumbnail from raw image bytes in memory."""
    img = Image.open(io.BytesIO(image_bytes))

    # Fix EXIF rotation
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
    except Exception:
        pass

    if img.mode != "RGB":
        img = img.convert("RGB")

    img.thumbnail((width, height), Image.LANCZOS)
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=80, optimize=True)
    return output.getvalue()


def estimate_image_quality(image_bytes: bytes) -> Dict[str, Any]:
    """Estimates image brightness, contrast, and blurriness for AI readiness."""
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    pixels = list(img.getdata())
    n = len(pixels)

    if n == 0:
        return {
            "quality_score": 0.0,
            "is_too_dark": True,
            "is_too_bright": False,
            "is_blurry": True,
            "is_usable": False,
            "recommendations": ["Image appears empty or invalid."]
        }

    mean_pixel = sum(pixels) / n
    variance = sum((p - mean_pixel) ** 2 for p in pixels) / n
    std_dev = math.sqrt(variance)

    # Edge detection for blur estimation
    edges = img.filter(ImageFilter.FIND_EDGES)
    edge_pixels = list(edges.getdata())
    edge_var = sum((p - (sum(edge_pixels) / len(edge_pixels))) ** 2 for p in edge_pixels) / len(edge_pixels)

    is_too_dark = mean_pixel < 45
    is_too_bright = mean_pixel > 215
    is_blurry = edge_var < 120

    recommendations: List[str] = []
    if is_too_dark:
        recommendations.append("Image is very dark. Ensure good lighting when taking photos.")
    if is_too_bright:
        recommendations.append("Image is overexposed or too bright.")
    if is_blurry:
        recommendations.append("Image appears blurry. Hold camera steady or re-focus.")

    score = 1.0
    if is_too_dark:
        score -= 0.3
    if is_too_bright:
        score -= 0.3
    if is_blurry:
        score -= 0.3
    if std_dev < 20:
        score -= 0.2
        recommendations.append("Low contrast image.")

    quality_score = max(0.0, min(1.0, round(score, 2)))
    is_usable = quality_score >= 0.4

    return {
        "quality_score": quality_score,
        "is_too_dark": is_too_dark,
        "is_too_bright": is_too_bright,
        "is_blurry": is_blurry,
        "is_usable": is_usable,
        "recommendations": recommendations if recommendations else ["Image quality is good."]
    }


def add_watermark(
    image_bytes: bytes,
    text: str = "Smart Community Platform",
    opacity: float = 0.3,
    position: str = "bottom-right"
) -> bytes:
    """Adds a semi-transparent text watermark onto an image."""
    base_img = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    w, h = base_img.size

    if w < 350 or h < 250:
        output = io.BytesIO()
        base_img.convert("RGB").save(output, format="JPEG", quality=85)
        return output.getvalue()

    txt_layer = Image.new("RGBA", base_img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(txt_layer)

    font_size = max(14, int(min(w, h) * 0.035))
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    margin = 15
    if position == "bottom-right":
        x = w - text_w - margin
        y = h - text_h - margin
    elif position == "bottom-left":
        x = margin
        y = h - text_h - margin
    elif position == "top-right":
        x = w - text_w - margin
        y = margin
    else:
        x = (w - text_w) // 2
        y = (h - text_h) // 2

    alpha = int(opacity * 255)
    draw.text((x, y), text, font=font, fill=(255, 255, 255, alpha))

    watermarked = Image.alpha_composite(base_img, txt_layer)
    output = io.BytesIO()
    watermarked.convert("RGB").save(output, format="JPEG", quality=85, optimize=True)
    return output.getvalue()


def prepare_for_ai_analysis(
    image_bytes: bytes,
    target_size: Tuple[int, int] = (640, 640)
) -> Dict[str, Any]:
    """Prepares image with letterboxing for YOLO/AI vision model inputs."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    orig_w, orig_h = img.size
    target_w, target_h = target_size

    scale = min(target_w / orig_w, target_h / orig_h)
    new_w = int(orig_w * scale)
    new_h = int(orig_h * scale)

    resized_img = img.resize((new_w, new_h), Image.LANCZOS)
    padded_img = Image.new("RGB", target_size, (128, 128, 128))

    pad_left = (target_w - new_w) // 2
    pad_top = (target_h - new_h) // 2
    padded_img.paste(resized_img, (pad_left, pad_top))

    out_buffer = io.BytesIO()
    padded_img.save(out_buffer, format="JPEG", quality=90)

    return {
        "processed_bytes": out_buffer.getvalue(),
        "original_width": orig_w,
        "original_height": orig_h,
        "processed_width": target_w,
        "processed_height": target_h,
        "padding_top": pad_top,
        "padding_left": pad_left,
        "scale_factor": scale
    }
