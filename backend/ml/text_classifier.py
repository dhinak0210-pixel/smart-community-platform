"""Text classification module using DistilBERT/DistilRoBERTa zero-shot and keyword fallback."""

import logging
import time
import asyncio
from typing import Optional, Any

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------------------
# CONSTANTS & CATEGORY MAPPINGS
# ------------------------------------------------------------------------------

CATEGORY_LABELS = [
    "infrastructure damage like roads potholes broken buildings",
    "waste management garbage trash dumping litter",
    "public safety crime theft vandalism danger fire",
    "environmental issues pollution trees parks",
    "utilities outage water electricity internet",
    "traffic and road signs signals accidents",
    "noise complaint construction music neighbors",
    "flooding water accumulation blocked drains",
    "other unspecified community issue"
]

CATEGORY_MAP = {
    "infrastructure damage like roads potholes broken buildings": "infrastructure",
    "waste management garbage trash dumping litter": "waste",
    "public safety crime theft vandalism danger fire": "safety",
    "environmental issues pollution trees parks": "environment",
    "utilities outage water electricity internet": "utilities",
    "traffic and road signs signals accidents": "traffic",
    "noise complaint construction music neighbors": "noise",
    "flooding water accumulation blocked drains": "flooding",
    "other unspecified community issue": "other"
}

URGENCY_LABELS = [
    "immediate danger life threatening emergency critical",
    "urgent affects many people serious problem high priority",
    "important issue needs attention medium priority",
    "minor inconvenience low priority can wait"
]

URGENCY_MAP = {
    "immediate danger life threatening emergency critical": "critical",
    "urgent affects many people serious problem high priority": "high",
    "important issue needs attention medium priority": "medium",
    "minor inconvenience low priority can wait": "low"
}

KEYWORD_RULES = {
    "safety": [
        "fire", "accident", "collapse", "dangerous", "crime",
        "theft", "explosion", "emergency", "injury", "unsafe",
        "attack", "flood danger", "gas leak"
    ],
    "infrastructure": [
        "pothole", "road", "crack", "broken", "bridge",
        "building", "sidewalk", "pavement", "wall collapse",
        "structure", "fence"
    ],
    "waste": [
        "garbage", "trash", "litter", "waste", "dump",
        "smell", "rats", "cockroach", "dirty", "rubbish"
    ],
    "flooding": [
        "flood", "water", "drain", "puddle", "overflow",
        "rain", "submerged", "waterlogged"
    ],
    "utilities": [
        "electricity", "power", "water supply", "internet",
        "cable", "outage", "blackout", "pipe", "leak"
    ],
    "traffic": [
        "traffic", "signal", "light", "sign", "parking",
        "accident", "congestion", "car", "vehicle"
    ],
    "noise": [
        "noise", "loud", "sound", "music", "construction",
        "vibration", "disturbing", "party"
    ],
    "environment": [
        "tree", "park", "pollution", "air", "smell",
        "smoke", "chemical", "green", "plant"
    ]
}

URGENCY_KEYWORDS = {
    "critical": [
        "fire", "collapse", "explosion", "emergency",
        "life", "danger", "immediately", "urgent", "gas leak",
        "flooding now", "injury", "accident happening"
    ],
    "high": [
        "several days", "many people", "affecting", "blocked",
        "no water", "no electricity", "unsafe", "hazard"
    ],
    "low": [
        "minor", "small", "little", "slight", "eventually",
        "whenever", "not urgent", "cosmetic"
    ]
}

STOP_WORDS = {
    "the", "is", "at", "on", "a", "an", "and", "or",
    "but", "in", "to", "it", "of", "for", "with",
    "this", "that", "was", "are", "has", "have",
    "been", "be", "will", "can", "my", "we", "our"
}


# ------------------------------------------------------------------------------
# MAIN CLASSIFICATION API
# ------------------------------------------------------------------------------

async def classify_issue_text(
    title: str,
    description: str,
    use_ml: bool = True
) -> dict[str, Any]:
    """Classify issue text into category and urgency level.
    
    Args:
        title: Issue title
        description: Full issue description
        use_ml: If True, try ML model first. If False, use keywords only.
        
    Returns:
        Dict with category, urgency, confidence scores, and keywords.
    """
    start = time.time()
    combined_text = f"{title}. {description}"
    combined_text_lower = combined_text.lower()

    if use_ml:
        ml_result = await _classify_with_model(combined_text)
        if ml_result is not None:
            ml_result["keywords_found"] = _extract_keywords(combined_text_lower)
            ml_result["processing_time_ms"] = int((time.time() - start) * 1000)
            ml_result["method_used"] = "ml_model"
            logger.info(
                f"Text classified via ML: category={ml_result['category']} "
                f"confidence={ml_result['category_confidence']:.2f}"
            )
            return ml_result

    keyword_result = _classify_with_keywords(combined_text_lower)
    keyword_result["processing_time_ms"] = int((time.time() - start) * 1000)
    keyword_result["method_used"] = "keyword_fallback"
    logger.info(
        f"Text classified via keywords: "
        f"category={keyword_result['category']} "
        f"confidence={keyword_result['category_confidence']:.2f}"
    )
    return keyword_result


# ------------------------------------------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------------------------------------------

async def _classify_with_model(text: str) -> Optional[dict[str, Any]]:
    """Use DistilBERT/DistilRoBERTa zero-shot classification model."""
    from backend.ml.model_manager import model_manager

    classifier = model_manager.get("text_classifier")
    if classifier is None:
        return None

    try:
        loop = asyncio.get_running_loop()
        trunc_text = text[:512]

        cat_task = loop.run_in_executor(
            None,
            lambda: classifier(trunc_text, CATEGORY_LABELS, multi_label=False)
        )
        urg_task = loop.run_in_executor(
            None,
            lambda: classifier(trunc_text, URGENCY_LABELS, multi_label=False)
        )

        category_result, urgency_result = await asyncio.gather(cat_task, urg_task)

        best_cat_label = category_result["labels"][0]
        best_cat_score = category_result["scores"][0]
        category = CATEGORY_MAP.get(best_cat_label, "other")

        best_urg_label = urgency_result["labels"][0]
        best_urg_score = urgency_result["scores"][0]
        urgency = URGENCY_MAP.get(best_urg_label, "medium")

        return {
            "category": category,
            "category_confidence": round(float(best_cat_score), 3),
            "urgency": urgency,
            "urgency_confidence": round(float(best_urg_score), 3),
            "raw_scores": {
                "categories": dict(zip(
                    [CATEGORY_MAP.get(l, l) for l in category_result["labels"]],
                    [round(float(s), 3) for s in category_result["scores"]]
                )),
                "urgency": dict(zip(
                    [URGENCY_MAP.get(l, l) for l in urgency_result["labels"]],
                    [round(float(s), 3) for s in urgency_result["scores"]]
                ))
            }
        }

    except Exception as e:
        logger.error(f"ML text classification failed: {e}")
        return None


def _classify_with_keywords(text_lower: str) -> dict[str, Any]:
    """Rule-based keyword classification as fallback."""
    category_scores: dict[str, int] = {}
    keywords_found: list[str] = []

    for cat, keywords in KEYWORD_RULES.items():
        score = 0
        found = []
        for kw in keywords:
            if kw in text_lower:
                score += 1
                found.append(kw)
        category_scores[cat] = score
        if found:
            keywords_found.extend(found)

    max_score = max(category_scores.values()) if category_scores else 0
    if max_score == 0:
        best_category = "other"
        category_confidence = 0.3
    else:
        best_category = max(category_scores, key=lambda k: category_scores[k])
        total_matched = sum(category_scores.values())
        category_confidence = min(
            0.9,
            (category_scores[best_category] / max(1, total_matched)) + 0.3
        )

    urgency = "medium"
    urgency_confidence = 0.5

    for kw in URGENCY_KEYWORDS["critical"]:
        if kw in text_lower:
            urgency = "critical"
            urgency_confidence = 0.85
            break

    if urgency == "medium":
        for kw in URGENCY_KEYWORDS["high"]:
            if kw in text_lower:
                urgency = "high"
                urgency_confidence = 0.75
                break

    if urgency == "medium":
        for kw in URGENCY_KEYWORDS["low"]:
            if kw in text_lower:
                urgency = "low"
                urgency_confidence = 0.75
                break

    return {
        "category": best_category,
        "category_confidence": round(category_confidence, 3),
        "urgency": urgency,
        "urgency_confidence": round(urgency_confidence, 3),
        "keywords_found": list(set(keywords_found)),
        "raw_scores": {
            "category_keyword_counts": category_scores
        }
    }


def _extract_keywords(text_lower: str) -> list[str]:
    """Extract matching domain keywords from text."""
    found: list[str] = []
    all_keywords: list[str] = []
    for keywords in KEYWORD_RULES.values():
        all_keywords.extend(keywords)

    for kw in all_keywords:
        if kw in text_lower and kw not in found:
            found.append(kw)

    return found[:10]


def generate_smart_tags(
    title: str,
    description: str,
    category: str,
    location_city: Optional[str]
) -> list[str]:
    """Generate searchable tags for an issue based on category, location, and keywords."""
    tags: set[str] = set()

    if category:
        tags.add(category)

    if location_city:
        tags.add(location_city.lower().replace(" ", "-"))

    text = f"{title} {description}".lower()
    found_kw = _extract_keywords(text)
    tags.update(found_kw)

    words = text.split()
    for word in words:
        cleaned = word.strip(".,!?;:'\"").lower()
        if len(cleaned) > 3 and cleaned not in STOP_WORDS and cleaned.isalpha():
            tags.add(cleaned)

    return sorted(list(tags))[:10]
