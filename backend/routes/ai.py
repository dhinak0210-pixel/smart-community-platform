"""FastAPI router for AI and ML intelligence layer endpoints."""

import logging
from typing import Optional
from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from backend.database import get_db
from backend.ml.model_manager import model_manager
from backend.ml.text_classifier import classify_issue_text
from backend.ml.image_analyzer import analyze_issue_image
from backend.ml.similarity_engine import find_similar_issues, semantic_search_issues
from backend.ml.hotspot_predictor import predict_hotspots
from backend.ml.groq_llm import answer_citizen_question, generate_authority_response
from backend.models.issue import Issue

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ai", tags=["AI & Machine Learning"])


# ------------------------------------------------------------------------------
# PYDANTIC REQUEST SCHEMAS
# ------------------------------------------------------------------------------

class TextClassifyRequest(BaseModel):
    title: str = Field(..., min_length=3, max_length=200, example="Pothole on Main Street")
    description: str = Field(..., min_length=5, max_length=2000, example="Large pothole causing traffic slowdown and potential vehicle damage.")
    use_ml: bool = Field(default=True, description="Try ML model before falling back to keywords")


class DuplicateCheckRequest(BaseModel):
    title: str = Field(..., min_length=3)
    description: str = Field(..., min_length=5)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    category: str = Field(..., example="infrastructure")
    exclude_uuid: Optional[str] = None


class AskQuestionRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=500, example="Are there any unresolved water leaks in Downtown?")


class AuthorityResponseRequest(BaseModel):
    issue_id: int = Field(..., gt=0, example=1)
    new_status: str = Field(default="in_progress", example="in_progress")
    department: Optional[str] = Field(default=None, example="Public Works")


# ------------------------------------------------------------------------------
# ENDPOINTS
# ------------------------------------------------------------------------------

@router.post("/classify-text", summary="Classify text title & description")
async def classify_text(payload: TextClassifyRequest):
    """Classify issue text into category and urgency level with confidence scores."""
    result = await classify_issue_text(
        title=payload.title,
        description=payload.description,
        use_ml=payload.use_ml
    )
    return result


@router.post("/analyze-image", summary="Analyze uploaded photo with YOLOv8")
async def analyze_image(
    file: UploadFile = File(...),
    title: Optional[str] = Form(""),
    description: Optional[str] = Form("")
):
    """Analyze image using YOLOv8 object detection with metadata fallbacks."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File must be an image (JPEG, PNG, WebP)"
        )

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image size exceeds 10MB limit"
        )

    result = await analyze_issue_image(
        image_bytes=image_bytes,
        issue_title=title or "",
        issue_description=description or ""
    )
    return result


@router.post("/check-duplicate", summary="Check for duplicate issues nearby")
async def check_duplicate(
    payload: DuplicateCheckRequest,
    db: Session = Depends(get_db)
):
    """Check for duplicate issues within 500m radius using semantic similarity."""
    result = await find_similar_issues(
        title=payload.title,
        description=payload.description,
        lat=payload.lat,
        lng=payload.lng,
        category=payload.category,
        db=db,
        exclude_uuid=payload.exclude_uuid
    )
    return result


@router.get("/hotspots", summary="Get predicted issue hotspots")
async def get_hotspots(
    days: int = Query(default=90, ge=7, le=365),
    db: Session = Depends(get_db)
):
    """Predict geographic hotspots and risk areas based on historical trends."""
    result = await predict_hotspots(db=db, days_history=days)
    return result


@router.post("/ask", summary="RAG-powered citizen question answering")
async def ask_question(
    payload: AskQuestionRequest,
    db: Session = Depends(get_db)
):
    """Answer citizen questions using ChromaDB vector search and Groq LLM."""
    semantic_results = await semantic_search_issues(
        query=payload.question, limit=5
    )

    total_issues = db.scalar(select(func.count(Issue.id)).where(Issue.deleted_at.is_(None))) or 0
    resolved_issues = db.scalar(
        select(func.count(Issue.id)).where(
            Issue.deleted_at.is_(None), Issue.status == "resolved"
        )
    ) or 0

    platform_stats = {
        "total": total_issues,
        "resolved": resolved_issues,
        "resolution_rate": (resolved_issues / max(1, total_issues)) * 100
    }

    answer = await answer_citizen_question(
        question=payload.question,
        relevant_issues=semantic_results,
        platform_stats=platform_stats
    )

    return {
        "question": payload.question,
        "answer": answer,
        "relevant_context_count": len(semantic_results),
        "source_issues": [r.get("uuid") for r in semantic_results]
    }


@router.get("/status", summary="Get AI model manager health status")
async def get_ai_status():
    """Get loading status, load times, and readiness of all 6 AI models."""
    return model_manager.get_status()


@router.post("/generate-response", summary="Generate authority response template")
async def generate_response(
    payload: AuthorityResponseRequest,
    db: Session = Depends(get_db)
):
    """Generate official response draft for authority updates using Groq LLM."""
    stmt = select(Issue).where(Issue.id == payload.issue_id)
    issue = db.execute(stmt).scalar_one_or_none()

    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {payload.issue_id} not found"
        )

    cat_str = issue.category.value if hasattr(issue.category, "value") else str(issue.category)

    response_draft = await generate_authority_response(
        issue_title=issue.title,
        issue_description=issue.description,
        issue_category=cat_str,
        current_status=payload.new_status,
        department=payload.department
    )

    return {
        "issue_id": payload.issue_id,
        "new_status": payload.new_status,
        "suggested_response": response_draft
    }
