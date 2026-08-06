"""NLP Issue Categorizer for automated category classification."""

import re
import logging
from backend.models.issue import IssueCategory

logger = logging.getLogger(__name__)

# Category keyword rules mapping
CATEGORY_KEYWORDS = {
    IssueCategory.POTHOLE: [
        r"\bpothole\b", r"\broad\b", r"\basphalt\b", r"\bcrater\b", r"\btarmac\b", r"\bcrack\b", r"\bstreet damage\b", r"\bhole\b"
    ],
    IssueCategory.STREET_LIGHT: [
        r"\bstreet\s*light\b", r"\blamp\b", r"\blight\b", r"\bdarkness\b", r"\bbulb\b", r"\bflicker\b", r"\bpole\b"
    ],
    IssueCategory.WATER_SUPPLY: [
        r"\bwater\b", r"\bpipe\b", r"\bleak\b", r"\bsewage\b", r"\bdrain\b", r"\boverflow\b", r"\bflooding\b", r"\btap\b"
    ],
    IssueCategory.WASTE_MANAGEMENT: [
        r"\bgarbage\b", r"\btrash\b", r"\bwaste\b", r"\bdump\b", r"\blitter\b", r"\bbin\b", r"\brefuse\b", r"\bodor\b"
    ],
    IssueCategory.TRAFFIC_SIGNAL: [
        r"\btraffic\b", r"\bsignal\b", r"\bred light\b", r"\bstoplight\b", r"\bintersection\b", r"\bcongestion\b"
    ],
    IssueCategory.PARK_MAINTENANCE: [
        r"\bpark\b", r"\btree\b", r"\bbench\b", r"\bplayground\b", r"\bgrass\b", r"\bgarden\b", r"\bweed\b"
    ],
}


def categorize_text(title: str, description: str) -> IssueCategory:
    """Predict issue category based on title and description text analysis."""
    text = f"{title} {description}".lower()

    category_scores = {cat: 0 for cat in CATEGORY_KEYWORDS}

    for category, regex_list in CATEGORY_KEYWORDS.items():
        for pattern in regex_list:
            matches = len(re.findall(pattern, text))
            category_scores[category] += matches

    best_category, highest_score = max(category_scores.items(), key=lambda item: item[1])

    if highest_score > 0:
        logger.info(f"Auto-categorized issue to '{best_category}' with score {highest_score}")
        return best_category

    return IssueCategory.OTHER
