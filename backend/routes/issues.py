"""Issue CRUD, Voting, and Discussion endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.issue import Issue, Vote, Comment, IssueCategory, IssueStatus
from backend.schemas.issue import (
    IssueCreate,
    IssueUpdate,
    IssueResponse,
    CommentCreate,
    CommentResponse,
    VoteResponse,
)
from backend.utils.auth import get_current_user
from backend.utils.upload import save_upload_file
from backend.ml.categorizer import categorize_text
from fastapi import File, UploadFile

router = APIRouter(prefix="/issues", tags=["Issues"])


@router.post("/auto-categorize", response_model=dict)
def auto_categorize_issue(payload: dict):
    """Predict issue category from title and description."""
    title = payload.get("title", "")
    description = payload.get("description", "")
    predicted_category = categorize_text(title, description)
    return {"predicted_category": predicted_category.value}


@router.post("/upload", response_model=dict)
async def upload_issue_image(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload an image photo for an issue report."""
    image_url = await save_upload_file(file)
    return {"image_url": image_url}


def format_issue_response(issue: Issue, db: Session) -> IssueResponse:
    """Helper to convert Issue ORM model into IssueResponse with aggregated vote & comment counts."""
    vote_count = db.query(func.count(Vote.id)).filter(Vote.issue_id == issue.id).scalar() or 0
    comment_count = db.query(func.count(Comment.id)).filter(Comment.issue_id == issue.id).scalar() or 0

    return IssueResponse(
        id=issue.id,
        title=issue.title,
        description=issue.description,
        category=issue.category,
        status=issue.status,
        priority=issue.priority,
        latitude=issue.latitude,
        longitude=issue.longitude,
        address=issue.address,
        image_url=issue.image_url,
        reporter_id=issue.reporter_id,
        assigned_to_id=issue.assigned_to_id,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
        reporter=issue.reporter,
        assigned_to=issue.assigned_to,
        vote_count=vote_count,
        comment_count=comment_count,
    )


@router.get("/", response_model=List[IssueResponse])
def list_issues(
    category: Optional[IssueCategory] = None,
    status: Optional[IssueStatus] = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retrieve community issues with optional category and status filtering."""
    query = db.query(Issue)
    if category:
        query = query.filter(Issue.category == category)
    if status:
        query = query.filter(Issue.status == status)

    issues = query.order_by(Issue.created_at.desc()).offset(skip).limit(limit).all()
    return [format_issue_response(issue, db) for issue in issues]


@router.post("/", response_model=IssueResponse, status_code=status.HTTP_201_CREATED)
def create_issue(
    issue_in: IssueCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Report a new community issue."""
    # Auto-categorize if category is unspecified or set to OTHER
    assigned_category = issue_in.category
    if assigned_category == IssueCategory.OTHER:
        assigned_category = categorize_text(issue_in.title, issue_in.description)

    new_issue = Issue(
        title=issue_in.title,
        description=issue_in.description,
        category=assigned_category,
        priority=issue_in.priority,
        latitude=issue_in.latitude,
        longitude=issue_in.longitude,
        address=issue_in.address,
        image_url=issue_in.image_url,
        reporter_id=current_user.id,
    )

    db.add(new_issue)
    db.commit()
    db.refresh(new_issue)
    return format_issue_response(new_issue, db)


@router.get("/{issue_id}", response_model=IssueResponse)
def get_issue(issue_id: int, db: Session = Depends(get_db)):
    """Get details of a specific issue by ID."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with ID {issue_id} not found."
        )
    return format_issue_response(issue, db)


@router.put("/{issue_id}", response_model=IssueResponse)
def update_issue(
    issue_id: int,
    issue_in: IssueUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update issue details or resolution status."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    # Restrict status changes to Authority or Admin roles
    if issue_in.status and current_user.role not in [UserRole.AUTHORITY, UserRole.ADMIN]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authorities can change issue status."
        )

    for field, value in issue_in.model_dump(exclude_unset=True).items():
        setattr(issue, field, value)

    db.commit()
    db.refresh(issue)
    return format_issue_response(issue, db)


@router.post("/{issue_id}/vote", response_model=VoteResponse)
def vote_issue(
    issue_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upvote an issue or remove vote if already voted."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    existing_vote = db.query(Vote).filter(
        Vote.issue_id == issue_id,
        Vote.user_id == current_user.id
    ).first()

    if existing_vote:
        # Toggle vote off
        db.delete(existing_vote)
        db.commit()
        raise HTTPException(status_code=status.HTTP_200_OK, detail="Vote removed successfully.")

    new_vote = Vote(issue_id=issue_id, user_id=current_user.id)
    db.add(new_vote)
    db.commit()
    db.refresh(new_vote)
    return new_vote


@router.post("/{issue_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    issue_id: int,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a discussion comment to an issue."""
    issue = db.query(Issue).filter(Issue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    new_comment = Comment(
        issue_id=issue_id,
        user_id=current_user.id,
        content=comment_in.content
    )
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment
