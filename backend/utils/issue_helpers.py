"""Utility helpers for Issue scoring, geospatial search, duplicate detection, tag extraction, and statistics."""

import math
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple, Optional
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.models.issue import Issue, IssueHistory, IssueStatus, IssuePriority, IssueCategory, ChangeType


def calculate_priority_score(issue: Issue) -> float:
    """Calculate numerical urgency priority score for issue ranking.

    Higher scores indicate higher resolution priority.
    Takes into account priority level, vote tally, age in days, and category weights.
    """
    priority_base = {
        IssuePriority.CRITICAL: 100.0,
        IssuePriority.HIGH: 70.0,
        IssuePriority.MEDIUM: 40.0,
        IssuePriority.LOW: 10.0,
    }
    
    category_weights = {
        IssueCategory.SAFETY: 1.5,
        IssueCategory.FLOODING: 1.4,
        IssueCategory.INFRASTRUCTURE: 1.3,
        IssueCategory.UTILITIES: 1.2,
        IssueCategory.TRAFFIC: 1.2,
        IssueCategory.WASTE: 1.1,
        IssueCategory.ENVIRONMENT: 1.0,
        IssueCategory.NOISE: 0.9,
        IssueCategory.OTHER: 1.0,
    }

    base = priority_base.get(issue.priority, 40.0)
    weight = category_weights.get(issue.category, 1.0)

    vote_bonus = (issue.vote_count or 0) * 2.0
    days_bonus = issue.days_open() * 1.5

    total_score = (base * weight) + vote_bonus + days_bonus
    return round(total_score, 2)


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate great-circle distance between two GPS coordinates in kilometers using Haversine formula."""
    R = 6371.0  # Earth radius in kilometers

    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))

    return R * c


def find_nearby_issues(
    db: Session,
    lat: float,
    lng: float,
    radius_km: float = 5.0,
) -> List[Tuple[Issue, float]]:
    """Return active issues within radius_km of given coordinates, sorted by distance."""
    # Bounding box optimization for initial SQL query
    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))

    query = db.query(Issue).filter(
        Issue.deleted_at == None,
        Issue.status.notin_([IssueStatus.RESOLVED, IssueStatus.REJECTED]),
        Issue.location_lat.between(lat - lat_delta, lat + lat_delta),
        Issue.location_lng.between(lng - lng_delta, lng + lng_delta),
    )

    results: List[Tuple[Issue, float]] = []
    for issue in query.all():
        dist = haversine_distance(lat, lng, issue.location_lat, issue.location_lng)
        if dist <= radius_km:
            results.append((issue, round(dist, 3)))

    results.sort(key=lambda x: x[1])
    return results


def detect_duplicate_issues(
    db: Session,
    new_issue: Issue,
    max_distance_m: float = 100.0,
) -> List[Dict[str, Any]]:
    """Find candidate duplicate issues within max_distance_m sharing category or text similarity."""
    radius_km = max_distance_m / 1000.0
    nearby = find_nearby_issues(db, new_issue.location_lat, new_issue.location_lng, radius_km=radius_km)

    new_words = set(re.findall(r"\w+", new_issue.title.lower()))
    candidates: List[Dict[str, Any]] = []

    for issue, dist_km in nearby:
        if issue.id == new_issue.id:
            continue
        
        # Calculate Jaccard similarity of title words
        existing_words = set(re.findall(r"\w+", issue.title.lower()))
        intersection = new_words.intersection(existing_words)
        union = new_words.union(existing_words)
        sim_score = (len(intersection) / len(union)) if union else 0.0

        if issue.category == new_issue.category or sim_score >= 0.3:
            candidates.append({
                "issue": issue,
                "distance_m": round(dist_km * 1000.0, 1),
                "similarity_score": round(sim_score, 2),
            })

    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return candidates


def generate_issue_tags(title: str, description: str) -> List[str]:
    """Extract up to 10 relevant lowercase search tags from title and description."""
    stop_words = {
        "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
        "by", "from", "up", "about", "into", "over", "after", "is", "are", "was", "were",
        "be", "been", "being", "have", "has", "had", "do", "does", "did", "this", "that",
        "there", "here", "very", "please", "help", "need", "near", "front", "road", "street"
    }
    text = f"{title} {description}".lower()
    words = re.findall(r"\b[a-z]{3,15}\b", text)

    tag_freq: Dict[str, int] = {}
    for word in words:
        if word not in stop_words:
            tag_freq[word] = tag_freq.get(word, 0) + 1

    sorted_tags = sorted(tag_freq.keys(), key=lambda w: tag_freq[w], reverse=True)
    return sorted_tags[:10]


def get_issue_statistics(db: Session) -> Dict[str, Any]:
    """Calculate aggregate platform statistics for dashboards and reporting."""
    total = db.query(func.count(Issue.id)).filter(Issue.deleted_at == None).scalar() or 0

    # Group by Status
    status_counts: Dict[str, int] = {}
    for s in IssueStatus:
        cnt = db.query(func.count(Issue.id)).filter(Issue.status == s, Issue.deleted_at == None).scalar() or 0
        status_counts[s.value] = cnt

    # Group by Category
    category_counts: Dict[str, int] = {}
    for c in IssueCategory:
        cnt = db.query(func.count(Issue.id)).filter(Issue.category == c, Issue.deleted_at == None).scalar() or 0
        category_counts[c.value] = cnt

    # Group by Priority
    priority_counts: Dict[str, int] = {}
    for p in IssuePriority:
        cnt = db.query(func.count(Issue.id)).filter(Issue.priority == p, Issue.deleted_at == None).scalar() or 0
        priority_counts[p.value] = cnt

    one_week_ago = datetime.utcnow() - timedelta(days=7)
    resolved_week = db.query(func.count(Issue.id)).filter(
        Issue.status == IssueStatus.RESOLVED,
        Issue.resolved_at >= one_week_ago,
        Issue.deleted_at == None
    ).scalar() or 0

    reported_week = db.query(func.count(Issue.id)).filter(
        Issue.created_at >= one_week_ago,
        Issue.deleted_at == None
    ).scalar() or 0

    # Calculate average resolution days
    resolved_issues = db.query(Issue).filter(
        Issue.status == IssueStatus.RESOLVED,
        Issue.resolved_at != None,
        Issue.deleted_at == None
    ).all()

    if resolved_issues:
        total_days = sum((img.resolved_at - img.created_at).total_seconds() / 86400.0 for img in resolved_issues if img.resolved_at)
        avg_days = round(total_days / len(resolved_issues), 1)
    else:
        avg_days = 0.0

    # Resolution rate percentage
    resolution_rate = round((status_counts.get("resolved", 0) / total * 100.0), 1) if total > 0 else 0.0

    # Top areas
    area_query = db.query(
        Issue.location_area, func.count(Issue.id).label("cnt")
    ).filter(
        Issue.location_area != None, Issue.deleted_at == None
    ).group_by(Issue.location_area).order_by(func.count(Issue.id).desc()).limit(5).all()

    top_areas = [{"area": area, "count": cnt} for area, cnt in area_query if area]

    return {
        "total_issues": total,
        "by_status": status_counts,
        "by_category": category_counts,
        "by_priority": priority_counts,
        "resolved_this_week": resolved_week,
        "reported_this_week": reported_week,
        "average_resolution_days": avg_days,
        "top_areas": top_areas,
        "resolution_rate": resolution_rate,
    }


def auto_close_stale_issues(db: Session) -> int:
    """Auto-close resolved issues that have gone 7 days without citizen confirmation."""
    cutoff = datetime.utcnow() - timedelta(days=7)
    stale_issues = db.query(Issue).filter(
        Issue.status == IssueStatus.RESOLVED,
        Issue.resolved_at <= cutoff,
        Issue.citizen_confirmed_resolved == None,
        Issue.deleted_at == None
    ).all()

    count = 0
    for issue in stale_issues:
        issue.citizen_confirmed_resolved = True
        issue.resolution_feedback = "Auto-closed after 7 days of inactivity."
        
        history_entry = IssueHistory(
            issue_id=issue.id,
            change_type=ChangeType.STATUS_CHANGE,
            old_value="resolved_pending_confirmation",
            new_value="confirmed_closed",
            note="Auto-closed by system due to 7 days without citizen feedback."
        )
        db.add(history_entry)
        count += 1

    if count > 0:
        db.commit()

    return count


def detect_potential_duplicates(
    db: Session,
    title: str,
    description: str,
    lat: float,
    lng: float,
    category: str
) -> List[Dict[str, Any]]:
    """Check for candidate duplicates using location radius (200m), category match, and title word overlap.

    Returns list of dicts: [{'issue_uuid': str, 'title': str, 'similarity_score': float, 'distance_m': float}]
    """
    radius_km = 0.2  # 200 meters
    nearby = find_nearby_issues(db, lat, lng, radius_km=radius_km)

    new_words = set(re.findall(r"\w+", title.lower()))
    candidates: List[Dict[str, Any]] = []

    for issue, dist_km in nearby:
        existing_words = set(re.findall(r"\w+", issue.title.lower()))
        intersection = new_words.intersection(existing_words)
        union = new_words.union(existing_words)
        sim_score = (len(intersection) / len(union)) if union else 0.0

        cat_val = issue.category.value if hasattr(issue.category, "value") else str(issue.category)
        if cat_val == category or sim_score >= 0.3:
            candidates.append({
                "issue_uuid": str(issue.uuid),
                "title": issue.title,
                "similarity_score": round(sim_score, 2),
                "distance_m": round(dist_km * 1000.0, 1),
            })

    candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
    return candidates


def build_issue_filters(
    status: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    city: Optional[str] = None,
    area: Optional[str] = None,
    reported_by_uuid: Optional[str] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate and clean filter parameters into a normalized dictionary ready for apply_filters."""
    filters: Dict[str, Any] = {}
    if status:
        filters["status"] = status.strip().lower()
    if category:
        filters["category"] = category.strip().lower()
    if priority:
        filters["priority"] = priority.strip().lower()
    if city:
        filters["location_city"] = city.strip()
    if area:
        filters["location_area"] = area.strip()
    if reported_by_uuid:
        filters["reported_by_uuid"] = reported_by_uuid.strip()
    if date_from:
        filters["date_from"] = date_from
    if date_to:
        filters["date_to"] = date_to
    if search:
        filters["search"] = search.strip()
    return filters

