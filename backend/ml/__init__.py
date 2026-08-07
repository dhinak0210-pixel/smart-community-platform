"""
Smart Community Platform - AI/ML Module

Models used:
- DistilBERT: text classification (category + urgency)
- YOLOv8n: image object detection
- MiniLM: semantic similarity + duplicate detection
- Random Forest: priority prediction
- Gradient Boosting: hotspot prediction
- Groq LLaMA: LLM for complex reasoning

All models run on CPU.
All models load once at startup.
All ML calls run in background to not block API.
Graceful fallback if any model fails.
"""

from .model_manager import ModelManager
from .text_classifier import classify_issue_text
from .image_analyzer import analyze_issue_image
from .similarity_engine import find_similar_issues
from .priority_predictor import predict_priority
from .hotspot_predictor import predict_hotspots

__all__ = [
    "ModelManager",
    "classify_issue_text",
    "analyze_issue_image",
    "find_similar_issues",
    "predict_priority",
    "predict_hotspots"
]
