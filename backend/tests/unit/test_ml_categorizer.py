"""Unit Tests — ML Categorizer and Text Classifier.

Tests the deterministic keyword-based categorization and tag generation
logic without requiring ML models or external APIs.
"""

import pytest
from backend.models.issue import IssueCategory
from backend.ml.categorizer import categorize_text
from backend.ml.text_classifier import (
    _classify_with_keywords,
    generate_smart_tags,
    _extract_keywords,
)


# ═══════════════════════════════════════════════════════════════════════════════
# Keyword Categorizer Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestCategorizerKeywords:
    """Verify the regex-based keyword categorizer correctly identifies issue types."""

    def test_pothole_categorized_as_infrastructure(self):
        result = categorize_text("Pothole on Main Road", "Big pothole causing accidents")
        assert result == IssueCategory.INFRASTRUCTURE

    def test_garbage_categorized_as_waste(self):
        result = categorize_text("Garbage overflow", "Trash bins overflowing with waste and dump")
        assert result == IssueCategory.WASTE

    def test_streetlight_categorized_as_utilities(self):
        result = categorize_text("Street light broken", "The lamp on pole near power line is flickering")
        assert result == IssueCategory.UTILITIES

    def test_flooding_categorized_correctly(self):
        result = categorize_text("Water flooding", "Drain overflow causing flooding on the street")
        assert result == IssueCategory.FLOODING

    def test_traffic_signal_categorized_correctly(self):
        result = categorize_text("Traffic signal broken", "The traffic signal at intersection is not working")
        assert result == IssueCategory.TRAFFIC

    def test_noise_complaint_categorized_correctly(self):
        result = categorize_text("Loud noise from construction", "Noise from construction disturbing residents")
        assert result == IssueCategory.NOISE

    def test_park_issue_categorized_as_environment(self):
        result = categorize_text("Park tree fallen", "A tree in the park fell on the bench")
        assert result == IssueCategory.ENVIRONMENT

    def test_safety_issue_categorized_correctly(self):
        result = categorize_text("Dangerous fire hazard", "Fire detected near unsafe building, very dangerous")
        assert result == IssueCategory.SAFETY

    def test_vague_text_returns_other(self):
        result = categorize_text("Something happened", "I want to report something")
        assert result == IssueCategory.OTHER

    def test_empty_text_returns_other(self):
        result = categorize_text("", "")
        assert result == IssueCategory.OTHER


# ═══════════════════════════════════════════════════════════════════════════════
# Keyword Classifier (Fallback) Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestKeywordClassifier:
    """Test the keyword-based fallback classifier."""

    def test_returns_category_and_confidence(self):
        result = _classify_with_keywords("pothole on road causing damage")
        assert "category" in result
        assert "category_confidence" in result
        assert "urgency" in result

    def test_critical_urgency_detected(self):
        result = _classify_with_keywords("there is a fire emergency dangerous collapse")
        assert result["urgency"] == "critical"

    def test_high_urgency_detected(self):
        result = _classify_with_keywords("no water supply affecting many people")
        assert result["urgency"] == "high"

    def test_low_urgency_detected(self):
        result = _classify_with_keywords("minor cosmetic damage low priority can wait")
        assert result["urgency"] == "low"

    def test_default_urgency_is_medium(self):
        result = _classify_with_keywords("there is a general issue in the area")
        assert result["urgency"] == "medium"

    def test_confidence_within_bounds(self):
        result = _classify_with_keywords("pothole road damage bridge sidewalk")
        assert 0.0 <= result["category_confidence"] <= 1.0

    def test_vague_text_low_confidence(self):
        result = _classify_with_keywords("something happened somewhere")
        assert result["category_confidence"] <= 0.5


# ═══════════════════════════════════════════════════════════════════════════════
# Smart Tag Generation Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestSmartTagGeneration:
    """Test tag extraction and generation."""

    def test_generates_tags_list(self):
        tags = generate_smart_tags(
            "Pothole on road", "Large pothole causing damage", "infrastructure", "TestCity"
        )
        assert isinstance(tags, list)
        assert len(tags) > 0

    def test_includes_category_tag(self):
        tags = generate_smart_tags(
            "Test issue", "Description of the issue goes here", "waste", "TestCity"
        )
        assert "waste" in tags

    def test_includes_city_tag(self):
        tags = generate_smart_tags(
            "Test issue", "Description of the issue goes here", "waste", "Test City"
        )
        assert "test-city" in tags

    def test_max_10_tags(self):
        long_desc = " ".join(["pothole road bridge sidewalk broken damage fence"] * 10)
        tags = generate_smart_tags("Long issue", long_desc, "infrastructure", "BigCity")
        assert len(tags) <= 10

    def test_extract_keywords_returns_list(self):
        kws = _extract_keywords("there is a pothole on the road near the bridge")
        assert isinstance(kws, list)
        assert "pothole" in kws
        assert "road" in kws

    def test_extract_keywords_max_10(self):
        long_text = " ".join(["pothole road bridge sidewalk crack fire garbage flood noise traffic electricity"] * 5)
        kws = _extract_keywords(long_text)
        assert len(kws) <= 10


# ═══════════════════════════════════════════════════════════════════════════════
# Issue Helper Tests
# ═══════════════════════════════════════════════════════════════════════════════

class TestIssueHelpers:
    """Test utility functions from issue_helpers module."""

    def test_haversine_distance_same_point_is_zero(self):
        from backend.utils.issue_helpers import haversine_distance
        dist = haversine_distance(12.9716, 77.5946, 12.9716, 77.5946)
        assert dist == 0.0

    def test_haversine_distance_known_cities(self):
        from backend.utils.issue_helpers import haversine_distance
        # New York to London ≈ 5570 km
        dist = haversine_distance(40.7128, -74.0060, 51.5074, -0.1278)
        assert 5500 < dist < 5700

    def test_generate_issue_tags(self):
        from backend.utils.issue_helpers import generate_issue_tags
        tags = generate_issue_tags("Pothole damage", "Road has a large pothole causing accidents")
        assert isinstance(tags, list)
        assert len(tags) <= 10
        assert "pothole" in tags or "damage" in tags

    def test_generate_tags_excludes_stop_words(self):
        from backend.utils.issue_helpers import generate_issue_tags
        tags = generate_issue_tags("The road is broken", "This is a broken road near the park")
        assert "the" not in tags
        assert "this" not in tags
