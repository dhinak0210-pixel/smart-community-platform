"""YOLOv8 vision analysis module for community issue detection."""

import logging
import time
import io
import asyncio
from datetime import datetime
from typing import Optional, Any
from PIL import Image as PILImage, ImageOps
import numpy as np

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# OBJECT & SCENE MAPPINGS
# ------------------------------------------------------------------------------

YOLO_TO_COMMUNITY: dict[str, dict[str, Any]] = {
    "car": {
        "category": "traffic",
        "priority": "low",
        "tags": ["vehicle", "traffic"]
    },
    "truck": {
        "category": "traffic",
        "priority": "low",
        "tags": ["vehicle", "traffic"]
    },
    "bus": {
        "category": "traffic",
        "priority": "low",
        "tags": ["vehicle", "transit"]
    },
    "pothole": {
        "category": "infrastructure",
        "priority": "high",
        "tags": ["pothole", "road-damage"]
    },
    "person": {
        "category": "safety",
        "priority": "medium",
        "tags": ["people"]
    },
    "fire hydrant": {
        "category": "utilities",
        "priority": "medium",
        "tags": ["water", "utilities"]
    },
    "stop sign": {
        "category": "traffic",
        "priority": "medium",
        "tags": ["traffic-sign"]
    },
    "bench": {
        "category": "infrastructure",
        "priority": "low",
        "tags": ["furniture", "public"]
    },
    "trash can": {
        "category": "waste",
        "priority": "low",
        "tags": ["waste"]
    },
    "bicycle": {
        "category": "traffic",
        "priority": "low",
        "tags": ["bicycle"]
    },
    "traffic light": {
        "category": "traffic",
        "priority": "high",
        "tags": ["traffic-light", "signal"]
    },
    "dog": {
        "category": "safety",
        "priority": "medium",
        "tags": ["animal", "stray"]
    },
    "cat": {
        "category": "safety",
        "priority": "low",
        "tags": ["animal"]
    }
}

SCENE_RULES = {
    "road_damage": {
        "indicators": ["car", "truck", "pothole", "traffic light", "stop sign"],
        "category": "infrastructure",
    },
    "waste_site": {
        "indicators": ["trash can"],
        "category": "waste",
    },
    "safety_hazard": {
        "indicators": ["person", "dog"],
        "category": "safety",
    }
}


# ------------------------------------------------------------------------------
# MAIN IMAGE ANALYSIS API
# ------------------------------------------------------------------------------

async def analyze_issue_image(
    image_bytes: bytes,
    issue_title: str = "",
    issue_description: str = ""
) -> dict[str, Any]:
    """Analyze uploaded issue photo using YOLOv8 with metadata fallback."""
    start = time.time()

    from backend.utils.image_optimizer import estimate_image_quality
    quality = estimate_image_quality(image_bytes)

    yolo_result = await _run_yolo_detection(image_bytes)

    if yolo_result is not None:
        processed = _process_yolo_results(
            yolo_result,
            issue_title,
            issue_description,
            quality
        )
        processed["method"] = "yolo"
        processed["success"] = True
        processed["image_quality"] = quality
        processed["processing_time_ms"] = int((time.time() - start) * 1000)
        processed["analyzed_at"] = datetime.utcnow().isoformat()

        logger.info(
            f"Image analyzed via YOLO: "
            f"detected={len(processed['detected_objects'])} objects "
            f"category={processed['suggested_category']} "
            f"confidence={processed['overall_confidence']:.2f}"
        )
        return processed

    metadata_result = _analyze_metadata_only(
        image_bytes, issue_title, issue_description, quality
    )
    metadata_result["method"] = "metadata_only"
    metadata_result["success"] = True
    metadata_result["image_quality"] = quality
    metadata_result["processing_time_ms"] = int((time.time() - start) * 1000)
    metadata_result["analyzed_at"] = datetime.utcnow().isoformat()

    logger.info("Image analyzed via metadata (YOLO unavailable)")
    return metadata_result


# ------------------------------------------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------------------------------------------

async def _run_yolo_detection(image_bytes: bytes) -> Optional[list[dict[str, Any]]]:
    """Run YOLOv8 inference asynchronously on CPU."""
    from backend.ml.model_manager import model_manager

    yolo = model_manager.get("yolo")
    if yolo is None:
        return None

    try:
        loop = asyncio.get_running_loop()

        def _predict_yolo() -> list[dict[str, Any]]:
            img = PILImage.open(io.BytesIO(image_bytes))
            img = ImageOps.exif_transpose(img)
            if img.mode != "RGB":
                img = img.convert("RGB")
            img_array = np.array(img)

            results = yolo(img_array, verbose=False, conf=0.25)
            detections = []
            if results and len(results) > 0:
                result = results[0]
                if result.boxes is not None:
                    for box in result.boxes:
                        conf = float(box.conf[0])
                        class_id = int(box.cls[0])
                        label = yolo.names[class_id]
                        xyxy = box.xyxy[0].tolist()

                        detections.append({
                            "label": str(label),
                            "confidence": round(conf, 3),
                            "bbox": [round(x, 1) for x in xyxy]
                        })
            detections.sort(key=lambda x: x["confidence"], reverse=True)
            return detections

        return await loop.run_in_executor(None, _predict_yolo)

    except Exception as e:
        logger.error(f"YOLO inference failed: {e}")
        return None


def _process_yolo_results(
    detections: list[dict[str, Any]],
    title: str,
    description: str,
    quality: dict[str, Any]
) -> dict[str, Any]:
    """Map raw YOLO detections to domain-specific category & priority."""
    enriched_detections = []
    for det in detections[:15]:
        community_info = YOLO_TO_COMMUNITY.get(det["label"])
        enriched_detections.append({
            **det,
            "community_relevance": (
                community_info["category"] if community_info else None
            )
        })

    relevant_detections = [
        d for d in enriched_detections
        if d["community_relevance"] is not None
    ]

    category_votes: dict[str, float] = {}
    for det in relevant_detections:
        cat = det["community_relevance"]
        weight = det["confidence"]
        category_votes[cat] = category_votes.get(cat, 0.0) + weight

    if category_votes:
        suggested_category = max(category_votes, key=lambda k: category_votes[k])
        total_weight = sum(category_votes.values())
        overall_confidence = min(
            0.95,
            category_votes[suggested_category] / max(1.0, total_weight)
        )
    else:
        suggested_category = "other"
        overall_confidence = 0.3

    suggested_priority = "medium"
    top_labels = [d["label"] for d in enriched_detections[:5]]

    if any(l in ["fire", "smoke", "person"] for l in top_labels):
        suggested_priority = "high"
    elif len(relevant_detections) > 5:
        suggested_priority = "high"
    elif quality.get("is_too_dark") or quality.get("is_blurry"):
        suggested_priority = "low"

    text_context = f"{title} {description}".lower()
    for urgency_kw in ["fire", "emergency", "danger", "collapse"]:
        if urgency_kw in text_context:
            suggested_priority = "critical"
            break

    top_object_names = [d["label"] for d in enriched_detections[:5]]
    notes = f"Detected {len(enriched_detections)} objects in image. "
    if top_object_names:
        notes += f"Top detections: {', '.join(top_object_names)}. "
    if quality.get("is_blurry"):
        notes += "Image is slightly blurry. "
    if quality.get("is_too_dark"):
        notes += "Image is dark. "

    return {
        "detected_objects": enriched_detections,
        "top_detections": top_object_names,
        "scene_type": _classify_scene(enriched_detections),
        "suggested_category": suggested_category,
        "suggested_priority": suggested_priority,
        "overall_confidence": round(float(overall_confidence), 3),
        "analysis_notes": notes
    }


def _analyze_metadata_only(
    image_bytes: bytes,
    title: str,
    description: str,
    quality: dict[str, Any]
) -> dict[str, Any]:
    """Fallback analysis using text context and image quality flags."""
    from backend.ml.text_classifier import KEYWORD_RULES

    analysis_notes = "Analysis based on image metadata. "
    text = f"{title} {description}".lower()
    suggested_category = "other"

    for category, keywords in KEYWORD_RULES.items():
        if any(kw in text for kw in keywords):
            suggested_category = category
            break

    if quality.get("is_too_dark"):
        analysis_notes += "Image is too dark for visual analysis. "
    if quality.get("is_blurry"):
        analysis_notes += "Image appears blurry. "

    return {
        "detected_objects": [],
        "top_detections": [],
        "scene_type": "unknown",
        "suggested_category": suggested_category,
        "suggested_priority": "medium",
        "overall_confidence": 0.3,
        "analysis_notes": analysis_notes
    }


def _classify_scene(detections: list[dict[str, Any]]) -> str:
    """Classify overall scene environment."""
    labels = [d["label"] for d in detections]
    if any(l in ["car", "truck", "bus", "traffic light", "stop sign"] for l in labels):
        return "road_or_traffic"
    elif any(l in ["person"] for l in labels):
        return "public_space"
    elif any(l in ["fire", "smoke"] for l in labels):
        return "emergency"
    else:
        return "general_infrastructure"
