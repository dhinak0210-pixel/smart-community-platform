"""Free tier ML: keyword rules + Groq API + HF API.
No PyTorch. No Transformers. No heavy models.
Fits easily within 512MB RAM on Render free tier.
"""

import logging
import re
import json
from typing import Optional, Dict, Any, List
import httpx

try:
    from backend.config import settings
except ImportError:
    from backend.config_free import free_settings as settings

logger = logging.getLogger(__name__)

CATEGORY_KEYWORDS = {
    "infrastructure": [
        "pothole", "road", "crack", "broken", "bridge",
        "building", "sidewalk", "pavement", "wall",
        "structure", "fence", "path", "curb", "asphalt",
        "concrete", "damaged", "collapse", "deteriorate"
    ],
    "waste": [
        "garbage", "trash", "litter", "waste", "dump",
        "smell", "rats", "cockroach", "dirty", "rubbish",
        "pile", "bags", "recycling", "bin", "overflow",
        "scattered", "illegal dumping"
    ],
    "safety": [
        "fire", "accident", "collapse", "dangerous", "crime",
        "theft", "explosion", "emergency", "injury", "unsafe",
        "attack", "gas leak", "electrical", "hazard", "risk",
        "vandalism", "violence", "fear", "threat"
    ],
    "flooding": [
        "flood", "water", "drain", "puddle", "overflow",
        "rain", "submerged", "waterlogged", "blocked drain",
        "accumulation", "sewage", "stagnant", "pipe burst"
    ],
    "utilities": [
        "electricity", "power", "water supply", "internet",
        "cable", "outage", "blackout", "pipe", "leak",
        "cut", "no water", "no power", "broken wire"
    ],
    "traffic": [
        "traffic", "signal", "light", "sign", "parking",
        "accident", "congestion", "car", "vehicle", "speed",
        "crossing", "roundabout", "junction", "road mark"
    ],
    "noise": [
        "noise", "loud", "sound", "music", "construction",
        "vibration", "disturbing", "party", "shouting",
        "horn", "drilling", "barking"
    ],
    "environment": [
        "tree", "park", "pollution", "air", "smell",
        "smoke", "chemical", "green", "plant", "fallen",
        "overgrown", "dead tree", "park damage"
    ]
}

URGENCY_KEYWORDS = {
    "critical": [
        "fire", "collapse", "explosion", "emergency",
        "life", "danger", "immediately", "urgent", "gas leak",
        "flood now", "injury", "accident happening", "help",
        "right now", "serious", "critical"
    ],
    "high": [
        "several days", "many people", "affecting", "blocked",
        "no water", "no electricity", "unsafe", "hazard",
        "week", "major", "affecting many"
    ],
    "low": [
        "minor", "small", "little", "slight", "eventually",
        "whenever", "not urgent", "cosmetic", "aesthetic"
    ]
}

STOPWORDS = {
    "the", "is", "at", "on", "a", "an", "and", "or",
    "but", "in", "to", "it", "of", "for", "with",
    "this", "that", "was", "are", "has", "have",
    "been", "be", "will", "can", "my", "we", "our",
    "there", "near", "around", "about", "from", "into"
}


async def classify_issue_lightweight(title: str, description: str) -> Dict[str, Any]:
    """Classify issue using Groq API -> HF API -> Keyword rules fallback."""
    combined = f"{title}. {description}".lower()

    # Step 1: Try Groq API (if GROQ_API_KEY available)
    groq_key = getattr(settings, "GROQ_API_KEY", None)
    if groq_key:
        try:
            result = await _classify_with_groq(title, description, groq_key)
            if result:
                result["method_used"] = "groq_llm"
                return result
        except Exception as e:
            logger.warning(f"Groq classification failed: {e}")

    # Step 2: Try Hugging Face Inference API
    hf_key = getattr(settings, "HUGGINGFACE_API_KEY", None)
    if hf_key:
        try:
            result = await _classify_with_hf_api(combined, hf_key)
            if result:
                result["method_used"] = "huggingface_api"
                return result
        except Exception as e:
            logger.warning(f"HF API classification failed: {e}")

    # Step 3: Keyword fallback (instant, zero RAM, zero cost)
    return _classify_with_keywords(combined)


async def _classify_with_groq(title: str, description: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Use Groq LLaMA 3 for zero-shot issue classification."""
    try:
        from groq import Groq
        client = Groq(api_key=api_key)
        prompt = f"""
Classify this community issue report. Return ONLY valid JSON, no explanation, no markdown.

Title: {title}
Description: {description[:400]}

Return this exact JSON format:
{{
  "category": "one of: infrastructure, waste, safety, environment, utilities, traffic, noise, flooding, other",
  "category_confidence": 0.85,
  "urgency": "one of: critical, high, medium, low",
  "urgency_confidence": 0.80,
  "keywords_found": ["keyword1", "keyword2"]
}}
"""
        response = client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=200,
            temperature=0.1
        )
        content = response.choices[0].message.content.strip()
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            parsed = json.loads(json_match.group())
            return {
                "category": parsed.get("category", "other"),
                "category_confidence": float(parsed.get("category_confidence", 0.7)),
                "urgency": parsed.get("urgency", "medium"),
                "urgency_confidence": float(parsed.get("urgency_confidence", 0.6)),
                "keywords_found": parsed.get("keywords_found", [])[:10]
            }
    except Exception as e:
        logger.warning(f"Groq execution failed: {e}")
    return None


async def _classify_with_hf_api(text: str, api_key: Optional[str]) -> Optional[Dict[str, Any]]:
    """Use Hugging Face zero-shot classification API."""
    CATEGORY_LABELS = [
        "infrastructure damage roads potholes buildings",
        "waste management garbage trash dumping",
        "public safety crime danger fire hazard",
        "environmental issues pollution trees parks",
        "utilities outage water electricity internet",
        "traffic signals signs road accidents",
        "noise complaint construction music",
        "flooding water drain blocked",
        "other community issue"
    ]
    HF_API_URL = "https://api-inference.huggingface.co/models/cross-encoder/nli-distilroberta-base"
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {"inputs": text[:500], "parameters": {"candidate_labels": CATEGORY_LABELS}}

    async with httpx.AsyncClient(timeout=15) as client:
        response = await client.post(HF_API_URL, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            best_label = data["labels"][0]
            best_score = data["scores"][0]

            LABEL_MAP = {
                "infrastructure damage roads potholes buildings": "infrastructure",
                "waste management garbage trash dumping": "waste",
                "public safety crime danger fire hazard": "safety",
                "environmental issues pollution trees parks": "environment",
                "utilities outage water electricity internet": "utilities",
                "traffic signals signs road accidents": "traffic",
                "noise complaint construction music": "noise",
                "flooding water drain blocked": "flooding",
                "other community issue": "other"
            }
            return {
                "category": LABEL_MAP.get(best_label, "other"),
                "category_confidence": round(best_score, 3),
                "urgency": "medium",
                "urgency_confidence": 0.5,
                "keywords_found": []
            }
    return None


def _classify_with_keywords(text_lower: str) -> Dict[str, Any]:
    """Pure keyword matching. Zero dependencies. Always works."""
    category_scores = {}
    keywords_found = []

    for category, keywords in CATEGORY_KEYWORDS.items():
        score = 0
        found = []
        for keyword in keywords:
            if keyword in text_lower:
                score += 1
                found.append(keyword)
        category_scores[category] = score
        keywords_found.extend(found)

    max_score = max(category_scores.values()) if category_scores else 0
    if max_score == 0:
        best_category = "other"
        category_confidence = 0.3
    else:
        best_category = max(category_scores, key=category_scores.get)
        total = sum(category_scores.values())
        category_confidence = min(0.88, (max_score / max(1, total)) * 1.5 + 0.3)

    urgency = "medium"
    urgency_confidence = 0.5

    for kw in URGENCY_KEYWORDS["critical"]:
        if kw in text_lower:
            urgency = "critical"
            urgency_confidence = 0.85
            break

    if urgency == "medium":
        low_kw_count = sum(1 for kw in URGENCY_KEYWORDS["low"] if kw in text_lower)
        high_kw_count = sum(1 for kw in URGENCY_KEYWORDS["high"] if kw in text_lower)
        if low_kw_count > high_kw_count:
            urgency = "low"
            urgency_confidence = 0.75
        elif high_kw_count > 0:
            urgency = "high"
            urgency_confidence = 0.70

    return {
        "category": best_category,
        "category_confidence": round(category_confidence, 3),
        "urgency": urgency,
        "urgency_confidence": round(urgency_confidence, 3),
        "keywords_found": list(set(keywords_found))[:10],
        "method_used": "keyword_fallback"
    }


def generate_tags_lightweight(title: str, description: str, category: str, city: Optional[str] = None) -> List[str]:
    """Generate tags without any ML model."""
    tags = set()
    tags.add(category)
    if city:
        tags.add(city.lower().replace(" ", "-"))

    text = f"{title} {description}".lower()
    words = re.findall(r'\b[a-z]{4,}\b', text)

    for cat, kws in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in text and len(kw) > 3:
                tags.add(kw.replace(" ", "-"))

    return sorted(list(tags))[:10]


def predict_priority_lightweight(
    category: str,
    title: str,
    description: str,
    vote_count: int = 0,
    has_image: bool = False
) -> Dict[str, Any]:
    """Rule-based priority prediction for free tier deployment."""
    text = f"{title} {description}".lower()
    CATEGORY_BASE_PRIORITY = {
        "safety": "critical",
        "flooding": "high",
        "infrastructure": "medium",
        "utilities": "medium",
        "traffic": "medium",
        "waste": "low",
        "noise": "low",
        "environment": "low",
        "other": "low"
    }

    base = CATEGORY_BASE_PRIORITY.get(category, "medium")
    critical_words = ["fire", "explosion", "collapse", "emergency", "gas leak", "electrocution", "life", "immediately"]

    for word in critical_words:
        if word in text:
            base = "critical"
            break

    if vote_count >= 50 and base != "critical":
        base = "critical"
    elif vote_count >= 20 and base == "low":
        base = "high"
    elif vote_count >= 10 and base == "low":
        base = "medium"

    confidence = 0.85 if base == "critical" else 0.70

    return {
        "priority": base,
        "confidence": confidence,
        "method": "rule_based_free_tier",
        "reasoning": [
            f"Category '{category}' mapped to {base} priority",
            f"Vote count ({vote_count}) evaluated",
            "Keyword safety rules checked"
        ]
    }
