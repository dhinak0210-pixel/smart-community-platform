"""Semantic similarity engine for duplicate detection and ChromaDB search."""

import logging
import time
import asyncio
from typing import Optional, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# DUPLICATE DETECTION API
# ------------------------------------------------------------------------------

async def find_similar_issues(
    title: str,
    description: str,
    lat: float,
    lng: float,
    category: str,
    db: Session,
    exclude_uuid: Optional[str] = None,
    limit: int = 5
) -> dict[str, Any]:
    """Find issues similar to a new report using semantic text similarity, geographic proximity, and category."""
    from backend.utils.issue_helpers import find_nearby_issues, haversine_distance

    # Candidates within 500m
    candidates = find_nearby_issues(
        db=db, lat=lat, lng=lng, radius_km=0.5, exclude_id=None
    )

    if exclude_uuid:
        candidates = [c for c in candidates if str(c.uuid) != str(exclude_uuid)]

    same_category = [
        c for c in candidates
        if hasattr(c.category, "value") and c.category.value == category
    ]

    if len(same_category) < 3:
        different_category = [
            c for c in candidates
            if not (hasattr(c.category, "value") and c.category.value == category)
        ]
        candidates_to_check = same_category + different_category[:5]
    else:
        candidates_to_check = same_category[:10]

    if not candidates_to_check:
        return {
            "similar_issues": [],
            "highest_similarity": 0.0,
            "is_duplicate_detected": False,
            "method": "no_candidates"
        }

    query_text = f"{title}. {description}"
    results = []

    for candidate in candidates_to_check:
        candidate_text = f"{candidate.title}. {candidate.description}"

        text_sim = await _calculate_text_similarity(query_text, candidate_text)

        distance_m = haversine_distance(
            lat, lng,
            candidate.location_lat, candidate.location_lng
        ) * 1000.0

        location_score = max(0.0, 1.0 - (distance_m / 500.0))
        cat_val = candidate.category.value if hasattr(candidate.category, "value") else str(candidate.category)
        category_bonus = 0.2 if cat_val == category else 0.0

        overall_sim = (
            text_sim * 0.6 +
            location_score * 0.3 +
            category_bonus * 0.1
        )

        status_val = candidate.status.value if hasattr(candidate.status, "value") else str(candidate.status)

        results.append({
            "uuid": str(candidate.uuid),
            "title": candidate.title,
            "category": cat_val,
            "status": status_val,
            "location_address": candidate.location_address or "",
            "distance_meters": round(distance_m, 1),
            "text_similarity": round(text_sim, 3),
            "location_score": round(location_score, 3),
            "overall_similarity": round(overall_sim, 3),
            "is_likely_duplicate": overall_sim > 0.75
        })

    results.sort(key=lambda x: x["overall_similarity"], reverse=True)
    top_results = results[:limit]
    highest_sim = top_results[0]["overall_similarity"] if top_results else 0.0

    return {
        "similar_issues": top_results,
        "highest_similarity": highest_sim,
        "is_duplicate_detected": highest_sim > 0.75,
        "method": "semantic_similarity"
    }


# ------------------------------------------------------------------------------
# TEXT SIMILARITY HELPER
# ------------------------------------------------------------------------------

async def _calculate_text_similarity(text1: str, text2: str) -> float:
    """Calculate semantic similarity using MiniLM embeddings or Jaccard fallback."""
    from backend.ml.model_manager import model_manager

    encoder = model_manager.get("sentence_transformer")

    if encoder is not None:
        try:
            loop = asyncio.get_running_loop()
            from sklearn.metrics.pairwise import cosine_similarity

            t1_trunc = text1[:512]
            t2_trunc = text2[:512]

            embeddings = await loop.run_in_executor(
                None,
                lambda: encoder.encode([t1_trunc, t2_trunc])
            )

            similarity = float(
                cosine_similarity(
                    embeddings[0].reshape(1, -1),
                    embeddings[1].reshape(1, -1)
                )[0][0]
            )
            return max(0.0, min(1.0, similarity))

        except Exception as e:
            logger.error(f"ML text similarity calculation failed: {e}")

    # Fallback: Jaccard keyword overlap
    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())
    stop_words = {"the", "is", "a", "an", "and", "or", "in", "on", "at", "to", "of", "for"}
    words1 -= stop_words
    words2 -= stop_words

    if not words1 and not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2
    return float(len(intersection) / len(union))


# ------------------------------------------------------------------------------
# CHROMADB VECTOR STORE
# ------------------------------------------------------------------------------

async def index_issue_in_chroma(
    issue_uuid: str,
    title: str,
    description: str,
    category: str,
    location_city: Optional[str]
) -> bool:
    """Index issue embedding in ChromaDB vector store."""
    from backend.ml.model_manager import model_manager

    collection = model_manager.get("issues_collection")
    encoder = model_manager.get("sentence_transformer")

    if collection is None or encoder is None:
        logger.warning("ChromaDB or encoder not available for indexing")
        return False

    try:
        text = f"{title}. {description}"
        loop = asyncio.get_running_loop()

        embedding = await loop.run_in_executor(
            None,
            lambda: encoder.encode(text[:512]).tolist()
        )

        await loop.run_in_executor(
            None,
            lambda: collection.upsert(
                ids=[str(issue_uuid)],
                embeddings=[embedding],
                documents=[text[:1000]],
                metadatas=[{
                    "uuid": str(issue_uuid),
                    "category": category or "other",
                    "city": location_city or "unknown"
                }]
            )
        )
        logger.debug(f"Issue indexed in ChromaDB: {issue_uuid}")
        return True

    except Exception as e:
        logger.error(f"ChromaDB indexing failed: {e}")
        return False


async def semantic_search_issues(
    query: str,
    limit: int = 10,
    category_filter: Optional[str] = None
) -> list[dict[str, Any]]:
    """Perform semantic vector search on indexed community issues."""
    from backend.ml.model_manager import model_manager

    collection = model_manager.get("issues_collection")
    encoder = model_manager.get("sentence_transformer")

    if collection is None or encoder is None:
        return []

    try:
        loop = asyncio.get_running_loop()

        query_embedding = await loop.run_in_executor(
            None,
            lambda: encoder.encode(query[:512]).tolist()
        )

        where_filter = None
        if category_filter:
            where_filter = {"category": category_filter}

        results = await loop.run_in_executor(
            None,
            lambda: collection.query(
                query_embeddings=[query_embedding],
                n_results=limit,
                where=where_filter
            )
        )

        formatted_results = []
        if results and "ids" in results and results["ids"] and len(results["ids"][0]) > 0:
            for i in range(len(results["ids"][0])):
                dist = results["distances"][0][i] if "distances" in results and results["distances"] else 0.0
                formatted_results.append({
                    "uuid": results["ids"][0][i],
                    "text": results["documents"][0][i] if "documents" in results else "",
                    "metadata": results["metadatas"][0][i] if "metadatas" in results else {},
                    "similarity": round(max(0.0, 1.0 - dist), 3)
                })

        return formatted_results

    except Exception as e:
        logger.error(f"Semantic search failed: {e}")
        return []
