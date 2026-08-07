"""Random Forest priority predictor module for community issues."""

import logging
import time
import asyncio
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# ENCODINGS & MAPS
# ------------------------------------------------------------------------------

CATEGORY_ENCODING = {
    "safety": 8,
    "flooding": 7,
    "infrastructure": 6,
    "utilities": 5,
    "traffic": 4,
    "waste": 3,
    "environment": 2,
    "noise": 1,
    "other": 0
}

PRIORITY_ENCODING = {
    "critical": 3,
    "high": 2,
    "medium": 1,
    "low": 0
}

PRIORITY_DECODING = {v: k for k, v in PRIORITY_ENCODING.items()}


# ------------------------------------------------------------------------------
# FEATURE ENGINEERING
# ------------------------------------------------------------------------------

def build_feature_vector(
    category: str,
    title: str,
    description: str,
    vote_count: int,
    has_image: bool,
    location_city: Optional[str],
    image_analysis: Optional[dict[str, Any]]
) -> list[float]:
    """Convert issue attributes into an 8-element numerical feature vector."""
    category_score = float(CATEGORY_ENCODING.get(category, 0))
    vote_count_capped = float(min(max(0, vote_count), 100))
    has_image_int = 1.0 if has_image else 0.0
    desc_word_count = float(min(len(description.split()), 200))

    text_lower = f"{title} {description}".lower()
    urgency_words = [
        "urgent", "immediately", "danger", "emergency",
        "critical", "serious", "dangerous", "blocked"
    ]
    has_urgency = 1.0 if any(w in text_lower for w in urgency_words) else 0.0

    safety_words = [
        "fire", "accident", "crime", "theft", "collapse",
        "unsafe", "hazard", "injury", "gas", "leak"
    ]
    has_safety = 1.0 if any(w in text_lower for w in safety_words) else 0.0

    ai_confidence = 0.5
    if image_analysis and "overall_confidence" in image_analysis:
        ai_confidence = float(image_analysis["overall_confidence"])

    title_words = max(1, len(title.split()))
    desc_words = max(1, len(description.split()))
    length_ratio = min(10.0, float(desc_words / title_words))

    return [
        category_score,
        vote_count_capped,
        has_image_int,
        desc_word_count,
        has_urgency,
        has_safety,
        ai_confidence,
        length_ratio
    ]


# ------------------------------------------------------------------------------
# MAIN PRIORITY PREDICTION API
# ------------------------------------------------------------------------------

async def predict_priority(
    category: str,
    title: str,
    description: str,
    vote_count: int = 0,
    has_image: bool = False,
    location_city: Optional[str] = None,
    image_analysis: Optional[dict[str, Any]] = None
) -> dict[str, Any]:
    """Predict priority using Random Forest model with rule-based fallback."""
    start = time.time()

    features = build_feature_vector(
        category, title, description, vote_count,
        has_image, location_city, image_analysis
    )

    from backend.ml.model_manager import model_manager
    model = model_manager.get("priority_model")

    if model is not None:
        try:
            loop = asyncio.get_running_loop()
            import numpy as np

            X = np.array([features])

            def _predict_rf():
                pred = model.predict(X)[0]
                proba = model.predict_proba(X)[0]
                return pred, proba

            prediction, probabilities = await loop.run_in_executor(None, _predict_rf)

            priority = PRIORITY_DECODING.get(int(prediction), "medium")
            confidence = float(np.max(probabilities))

            reasoning = _build_reasoning(
                features, priority, category, vote_count, has_image
            )

            feature_importance = {}
            if hasattr(model, "feature_importances_"):
                feature_names = [
                    "category_score", "vote_count", "has_image",
                    "description_length", "has_urgency_words",
                    "has_safety_words", "ai_image_confidence",
                    "text_length_ratio"
                ]
                importances = model.feature_importances_
                feature_importance = {
                    name: round(float(imp), 3)
                    for name, imp in zip(feature_names, importances)
                }

            logger.info(
                f"Priority predicted: {priority} "
                f"confidence={confidence:.2f} method=random_forest"
            )

            return {
                "priority": priority,
                "confidence": round(confidence, 3),
                "method": "random_forest",
                "reasoning": reasoning,
                "feature_importance": feature_importance,
                "processing_time_ms": int((time.time() - start) * 1000)
            }

        except Exception as e:
            logger.error(f"Random Forest priority prediction failed: {e}")

    rule_result = _rule_based_priority(
        category, title, description, vote_count, has_image
    )
    rule_result["processing_time_ms"] = int((time.time() - start) * 1000)
    logger.info(f"Priority via rules: {rule_result['priority']}")
    return rule_result


# ------------------------------------------------------------------------------
# HELPERS & RULE-BASED FALLBACK
# ------------------------------------------------------------------------------

def _rule_based_priority(
    category: str,
    title: str,
    description: str,
    vote_count: int,
    has_image: bool
) -> dict[str, Any]:
    """Rule-based priority classifier fallback."""
    text = f"{title} {description}".lower()
    reasoning = []

    critical_indicators = [
        "fire", "collapse", "emergency", "gas leak",
        "electrocution", "flood danger", "explosion"
    ]

    if category == "safety" or any(w in text for w in critical_indicators):
        priority = "critical"
        reasoning.append("Safety issue or critical keyword detected")
    elif category == "flooding" and vote_count > 5:
        priority = "high"
        reasoning.append("Flooding with community concern")
    elif vote_count > 20:
        priority = "high"
        reasoning.append(f"High community interest: {vote_count} votes")
    elif vote_count > 10 or category in ["infrastructure", "utilities"]:
        priority = "medium"
        reasoning.append("Standard infrastructure or utility issue")
    else:
        priority = "low"
        reasoning.append("Low engagement, minor issue")

    return {
        "priority": priority,
        "confidence": 0.6,
        "method": "rule_based",
        "reasoning": reasoning,
        "feature_importance": {}
    }


def _build_reasoning(
    features: list[float],
    priority: str,
    category: str,
    vote_count: int,
    has_image: bool
) -> list[str]:
    """Build human-readable explanations for ML decisions."""
    reasoning = []
    if features[4] == 1.0:
        reasoning.append("Contains urgency indicators in description")
    if features[5] == 1.0:
        reasoning.append("Safety-related keywords detected")
    if features[1] > 10:
        reasoning.append(f"High community interest ({vote_count} votes)")
    if features[0] >= 6:
        reasoning.append(f"High-priority category: {category}")
    if has_image and features[6] > 0.7:
        reasoning.append("Image analysis confirms severity")
    if not reasoning:
        reasoning.append("Based on category, description, and engagement level")

    return reasoning
