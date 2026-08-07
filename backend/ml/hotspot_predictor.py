"""Hotspot prediction module for identifying geographic issue clusters and forecasting risk."""

import logging
import time
from datetime import datetime, timedelta
from typing import Any
from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session

from backend.models.issue import Issue, IssueCategory

logger = logging.getLogger(__name__)


async def predict_hotspots(db: Session, days_history: int = 90) -> dict[str, Any]:
    """Analyze historical issue data to predict future problem hotspots and risk areas."""
    start = time.time()
    logger.info(f"Starting hotspot prediction (last {days_history} days)")

    cutoff_date = datetime.utcnow() - timedelta(days=days_history)

    stmt = (
        select(
            Issue.location_area,
            Issue.location_city,
            Issue.category,
            Issue.created_at,
            Issue.vote_count
        )
        .where(
            and_(
                Issue.created_at >= cutoff_date,
                Issue.deleted_at.is_(None),
                Issue.location_area.isnot(None)
            )
        )
    )

    rows = db.execute(stmt).all()

    area_data: dict[str, dict[str, Any]] = {}

    for area, city, cat, created_at, vote_count in rows:
        if not area:
            continue

        cat_str = cat.value if hasattr(cat, "value") else str(cat)
        city_str = city or "Unknown City"

        if area not in area_data:
            area_data[area] = {
                "area": area,
                "city": city_str,
                "total_issues": 0,
                "categories": {},
                "votes": [],
                "created_timestamps": []
            }

        data = area_data[area]
        data["total_issues"] += 1
        data["categories"][cat_str] = data["categories"].get(cat_str, 0) + 1
        data["votes"].append(vote_count or 0)
        data["created_timestamps"].append(created_at)

    high_risk_areas = []
    city_aggregates: dict[str, int] = {}
    category_totals: dict[str, int] = {}

    for area_name, data in area_data.items():
        city_name = data["city"]
        total_issues = data["total_issues"]
        city_aggregates[city_name] = city_aggregates.get(city_name, 0) + total_issues

        dominant_category = max(data["categories"], key=lambda k: data["categories"][k])
        for cat, cnt in data["categories"].items():
            category_totals[cat] = category_totals.get(cat, 0) + cnt

        avg_votes = sum(data["votes"]) / max(1, len(data["votes"]))

        now = datetime.utcnow()
        recent_cutoff = now - timedelta(days=int(days_history / 2))
        recent_count = sum(1 for ts in data["created_timestamps"] if ts >= recent_cutoff)
        older_count = total_issues - recent_count

        if recent_count > older_count * 1.2:
            trend = "increasing"
            trend_multiplier = 1.3
        elif recent_count < older_count * 0.8:
            trend = "decreasing"
            trend_multiplier = 0.7
        else:
            trend = "stable"
            trend_multiplier = 1.0

        if dominant_category == "safety":
            cat_weight = 1.5
        elif dominant_category == "flooding":
            cat_weight = 1.3
        elif dominant_category == "infrastructure":
            cat_weight = 1.1
        else:
            cat_weight = 1.0

        base_score = total_issues * 2.0
        vote_bonus = avg_votes * 0.5
        risk_score = min(100.0, (base_score * trend_multiplier * cat_weight) + vote_bonus)

        avg_per_week = total_issues / max(1.0, (days_history / 7.0))
        if trend == "increasing":
            pred_next_week = int(round(avg_per_week * 1.3))
        elif trend == "decreasing":
            pred_next_week = int(round(avg_per_week * 0.7))
        else:
            pred_next_week = int(round(avg_per_week))

        high_risk_areas.append({
            "area": area_name,
            "city": city_name,
            "risk_score": round(risk_score, 1),
            "predicted_issues_next_week": max(1, pred_next_week),
            "dominant_category": dominant_category,
            "historical_count": total_issues,
            "trend": trend
        })

    high_risk_areas.sort(key=lambda x: x["risk_score"], reverse=True)
    top_risk_areas = high_risk_areas[:10]

    category_trends = {
        cat: {
            "count": cnt,
            "percentage": round((cnt / max(1, len(rows))) * 100, 1)
        }
        for cat, cnt in category_totals.items()
    }

    return {
        "high_risk_areas": top_risk_areas,
        "city_predictions": city_aggregates,
        "category_trends": category_trends,
        "model_confidence": 0.75,
        "analysis_period_days": days_history,
        "generated_at": datetime.utcnow().isoformat(),
        "processing_time_ms": int((time.time() - start) * 1000)
    }
