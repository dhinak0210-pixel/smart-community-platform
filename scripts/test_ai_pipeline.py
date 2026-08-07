#!/usr/bin/env python3
"""Comprehensive test script for Smart Community Platform AI/ML pipeline."""

import os
import sys
import asyncio
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


async def main():
    logger.info("=== Testing ModelManager ===")
    from backend.ml.model_manager import model_manager
    results = model_manager.load_all_models()
    logger.info(f"ModelManager load results: {results}")
    status = model_manager.get_status()
    logger.info(f"Model status summary: {status}")

    logger.info("\n=== Testing Text Classifier ===")
    from backend.ml.text_classifier import classify_issue_text
    res_text = await classify_issue_text(
        title="Pothole on Main Street",
        description="Large pothole in middle of road causing severe traffic slowdown and vehicle damage."
    )
    logger.info(f"Text classification result: category={res_text['category']}, urgency={res_text['urgency']}, method={res_text['method_used']}")
    assert res_text["category"] in ["infrastructure", "traffic"], f"Unexpected category: {res_text['category']}"

    logger.info("\n=== Testing Image Analyzer ===")
    from backend.ml.image_analyzer import analyze_issue_image
    from PIL import Image as PILImage
    import io

    # Create dummy RGB image
    img = PILImage.new("RGB", (300, 300), color=(100, 150, 200))
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format="JPEG")
    dummy_bytes = img_byte_arr.getvalue()

    res_img = await analyze_issue_image(
        image_bytes=dummy_bytes,
        issue_title="Broken road surface",
        issue_description="Pothole on road"
    )
    logger.info(f"Image analysis result: method={res_img['method']}, category={res_img['suggested_category']}")
    assert res_img["success"] is True

    logger.info("\n=== Testing Priority Predictor ===")
    from backend.ml.priority_predictor import predict_priority
    res_prio = await predict_priority(
        category="safety",
        title="Fire hazard at gas station",
        description="Leaking fuel pump next to electrical wire causing immediate dangerous fire emergency",
        vote_count=15,
        has_image=True
    )
    logger.info(f"Priority prediction result: priority={res_prio['priority']}, confidence={res_prio['confidence']}, method={res_prio['method']}")
    assert res_prio["priority"] in ["critical", "high"], f"Unexpected priority: {res_prio['priority']}"

    logger.info("\n=== Testing Hotspot Predictor & Database ===")
    from backend.database import SessionLocal, init_db
    from backend.ml.hotspot_predictor import predict_hotspots

    init_db()
    db = SessionLocal()
    try:
        res_hotspot = await predict_hotspots(db, days_history=90)
        logger.info(f"Hotspot prediction result: high_risk_areas_count={len(res_hotspot['high_risk_areas'])}")
    finally:
        db.close()

    logger.info("\n=== ALL AI/ML PIPELINE COMPONENT TESTS PASSED SUCESSFULLY! ===")


if __name__ == "__main__":
    asyncio.run(main())
