"""Complete AI pipeline for automated issue classification, vision analysis, priority scoring, and indexing."""

import logging
import time
from datetime import datetime
from typing import Optional, Any, Callable

from backend.config import settings
from backend.ml.text_classifier import classify_issue_text, generate_smart_tags
from backend.ml.image_analyzer import analyze_issue_image
from backend.ml.similarity_engine import find_similar_issues, index_issue_in_chroma
from backend.ml.priority_predictor import predict_priority

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# MAIN PIPELINE
# ------------------------------------------------------------------------------

async def process_new_issue(
    issue_uuid: str,
    title: str,
    description: str,
    lat: float,
    lng: float,
    location_city: Optional[str],
    category: Optional[str],
    image_bytes: Optional[bytes],
    db: Any,
    auto_apply: bool = True
) -> dict[str, Any]:
    """Execute complete AI processing pipeline for a reported issue."""
    start = time.time()
    logger.info(f"Starting AI pipeline for issue: {issue_uuid}")

    # Step 1: Text Analysis
    logger.info(f"Pipeline step 1/4: Text classification")
    text_result = await classify_issue_text(title, description)

    # Step 2: Image Analysis (if present)
    image_result = None
    if image_bytes:
        logger.info(f"Pipeline step 2/4: Image analysis")
        from backend.utils.image_optimizer import prepare_for_ai_analysis
        prep = prepare_for_ai_analysis(image_bytes)
        image_result = await analyze_issue_image(
            prep["processed_bytes"],
            title,
            description
        )
    else:
        logger.info("Pipeline step 2/4: Skipped (no image)")

    # Step 3: Similarity Check
    logger.info(f"Pipeline step 3/4: Similarity detection")
    similarity_result = await find_similar_issues(
        title=title,
        description=description,
        lat=lat,
        lng=lng,
        category=text_result["category"],
        db=db,
        exclude_uuid=issue_uuid
    )

    # Step 4: Priority Prediction
    logger.info(f"Pipeline step 4/4: Priority prediction")
    priority_result = await predict_priority(
        category=text_result["category"],
        title=title,
        description=description,
        vote_count=0,
        has_image=image_bytes is not None,
        location_city=location_city,
        image_analysis=image_result
    )

    # Step 5: Final Resolution Rules
    if (
        image_result
        and image_result.get("overall_confidence", 0.0) > 0.7
        and text_result["category_confidence"] < 0.6
    ):
        final_category = image_result["suggested_category"]
    elif text_result["category_confidence"] > 0.6:
        final_category = text_result["category"]
    elif category and category != "other":
        final_category = category
    else:
        final_category = "other"

    final_priority = priority_result["priority"]

    final_tags = generate_smart_tags(
        title, description, final_category, location_city
    )

    # Step 6: Auto-apply DB Updates
    changes_made = []
    auto_applied = False

    if auto_apply:
        from sqlalchemy import select
        from backend.models.issue import Issue, IssueHistory, ChangeType, IssueCategory, IssuePriority

        stmt = select(Issue).where(Issue.uuid == issue_uuid)
        issue = db.execute(stmt).scalar_one_or_none()

        if issue:
            current_cat = issue.category.value if hasattr(issue.category, "value") else str(issue.category)
            current_pri = issue.priority.value if hasattr(issue.priority, "value") else str(issue.priority)

            # Auto-apply category if confidence is high and manual override not set
            if (
                text_result["category_confidence"] >= settings.ML_AUTO_APPLY_THRESHOLD
                and current_cat == "other"
                and not getattr(issue, "manual_priority_override", False)
            ):
                try:
                    issue.category = IssueCategory(final_category)
                    changes_made.append(f"category: {current_cat} → {final_category}")
                    auto_applied = True
                except ValueError:
                    pass

            # Auto-apply priority if confidence is high and manual override not set
            if (
                priority_result["confidence"] >= settings.ML_AUTO_APPLY_THRESHOLD
                and not getattr(issue, "manual_priority_override", False)
            ):
                try:
                    issue.priority = IssuePriority(final_priority)
                    changes_made.append(f"priority: {current_pri} → {final_priority}")
                    auto_applied = True
                except ValueError:
                    pass

            issue.ai_suggested_category = final_category
            issue.ai_category_confidence = text_result["category_confidence"]
            issue.ai_suggested_priority = final_priority
            issue.ai_image_analysis = image_result
            issue.ai_tags = final_tags
            issue.ai_processed = True
            issue.ai_processed_at = datetime.utcnow()
            issue.similarity_score = similarity_result["highest_similarity"]

            if changes_made:
                history_entry = IssueHistory(
                    issue_id=issue.id,
                    changed_by=1,
                    change_type=ChangeType.AI_UPDATE,
                    old_value="pending",
                    new_value=f"AI processed: {', '.join(changes_made)}",
                    note="Auto-applied by AI analysis pipeline"
                )
                db.add(history_entry)

            db.commit()
            logger.info(
                f"AI results saved for issue {issue_uuid}. Changes: {changes_made}"
            )

    # Step 7: Index in ChromaDB
    await index_issue_in_chroma(
        issue_uuid=issue_uuid,
        title=title,
        description=description,
        category=final_category,
        location_city=location_city
    )

    processing_time = int((time.time() - start) * 1000)

    result = {
        "text_analysis": text_result,
        "image_analysis": image_result,
        "similarity": similarity_result,
        "priority_prediction": priority_result,
        "final_category": final_category,
        "final_priority": final_priority,
        "final_tags": final_tags,
        "auto_applied": auto_applied,
        "changes_made": changes_made,
        "processing_time_ms": processing_time,
        "pipeline_version": "1.0.0"
    }

    logger.info(
        f"AI pipeline complete for {issue_uuid}: "
        f"category={final_category} priority={final_priority} "
        f"time={processing_time}ms changes={changes_made}"
    )

    return result


# ------------------------------------------------------------------------------
# BACKGROUND TASK WRAPPER
# ------------------------------------------------------------------------------

async def run_pipeline_background(
    issue_uuid: str,
    title: str,
    description: str,
    lat: float,
    lng: float,
    location_city: Optional[str],
    category: Optional[str],
    image_url: Optional[str],
    db_session_factory: Callable[[], Any]
) -> None:
    """Wrapper task to run complete AI processing in FastAPI BackgroundTasks."""
    try:
        image_bytes = None
        if image_url:
            try:
                import httpx
                # Handle relative upload paths vs absolute URLs
                fetch_url = image_url
                if fetch_url.startswith("/uploads/"):
                    import os
                    file_path = "." + fetch_url
                    if os.path.exists(file_path):
                        with open(file_path, "rb") as f:
                            image_bytes = f.read()
                elif fetch_url.startswith("http"):
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        response = await client.get(fetch_url)
                        if response.status_code == 200:
                            image_bytes = response.content
            except Exception as e:
                logger.warning(f"Could not fetch image for AI pipeline: {e}")

        db = db_session_factory()
        try:
            await process_new_issue(
                issue_uuid=issue_uuid,
                title=title,
                description=description,
                lat=lat,
                lng=lng,
                location_city=location_city,
                category=category,
                image_bytes=image_bytes,
                db=db,
                auto_apply=True
            )
        finally:
            db.close()

    except Exception as e:
        logger.error(
            f"Background AI pipeline failed for issue {issue_uuid}: {e}",
            exc_info=True
        )
