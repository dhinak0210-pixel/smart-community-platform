"""User profile, leaderboard, and administration endpoints for Smart Community Platform."""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import desc

from backend.database import get_db
from backend.models.user import User, UserRole
from backend.models.issue import Issue, IssueStatus
from backend.schemas.user import (
    UserResponse,
    UserProfileResponse,
    UserPublicResponse,
    UserListResponse,
)
from backend.schemas.issue import IssueListResponse, IssueSummary
from backend.utils.auth import (
    get_current_user,
    get_optional_user,
    require_admin,
)
from backend.utils.db_utils import paginate

router = APIRouter(tags=["Users"])
logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. GET /api/users/leaderboard (Must be placed before /{uuid} route)
# ------------------------------------------------------------------------------
@router.get("/leaderboard", response_model=Dict[str, Any])
def get_user_leaderboard(
    limit: int = Query(default=20, ge=1, le=100, description="Top N users"),
    db: Session = Depends(get_db),
):
    """Retrieve top active and verified users ranked by reputation score."""
    top_users = (
        db.query(User)
        .filter(User.is_active == True, User.is_verified == True, User.deleted_at == None)
        .order_by(desc(User.reputation_score))
        .limit(limit)
        .all()
    )

    leaderboard_data = []
    for rank, u in enumerate(top_users, start=1):
        leaderboard_data.append({
            "rank": rank,
            "user": UserPublicResponse.model_validate(u),
            "score": float(u.reputation_score or 0.0),
        })

    return {"leaderboard": leaderboard_data}


# ------------------------------------------------------------------------------
# 2. GET /api/users/ (List users - Admin only)
# ------------------------------------------------------------------------------
@router.get("/", response_model=UserListResponse)
def list_users(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    role: Optional[UserRole] = Query(default=None, description="Filter by user role"),
    is_active: Optional[bool] = Query(default=None, description="Filter by active status"),
    is_verified: Optional[bool] = Query(default=None, description="Filter by email verification status"),
    search: Optional[str] = Query(default=None, description="Search by name or email"),
    sort_by: str = Query(default="created_at", description="Sort field"),
    sort_order: str = Query(default="desc", description="Sort order (asc/desc)"),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Paginated user directory listing accessible strictly by Administrators."""
    query = db.query(User).filter(User.deleted_at == None)

    if role:
        query = query.filter(User.role == role)
    if is_active is not None:
        query = query.filter(User.is_active == is_active)
    if is_verified is not None:
        query = query.filter(User.is_verified == is_verified)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            (User.name.ilike(search_term)) | (User.email.ilike(search_term))
        )

    # Validate and apply dynamic sorting
    sort_column = getattr(User, sort_by, User.created_at)
    if sort_order.lower() == "asc":
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    items, total, total_pages = paginate(query, page=page, page_size=page_size)

    public_users = [UserPublicResponse.model_validate(u) for u in items]

    return UserListResponse(
        users=public_users,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


# ------------------------------------------------------------------------------
# 3. GET /api/users/{uuid} (Public or self user profile)
# ------------------------------------------------------------------------------
@router.get("/{user_uuid}", response_model=Any)
def get_user_by_uuid(
    user_uuid: UUID,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db),
):
    """Get public profile of any active user, or detailed profile if requesting self."""
    user = db.query(User).filter(User.uuid == user_uuid, User.deleted_at == None).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    # 404 for inactive/banned users unless requester is admin
    if not user.is_active:
        if not current_user or current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found.",
            )

    # Return full UserProfileResponse if requester is viewing their own profile
    if current_user and current_user.id == user.id:
        return UserProfileResponse.model_validate(user)

    return UserPublicResponse.model_validate(user)


# ------------------------------------------------------------------------------
# 4. PUT /api/users/{uuid}/ban (Ban or unban user - Admin only)
# ------------------------------------------------------------------------------
@router.put("/{user_uuid}/ban", response_model=UserResponse)
def ban_unban_user(
    user_uuid: UUID,
    body: Dict[str, Any],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Deactivate (ban) or reactivate (unban) a user account. Restricted to Administrators."""
    target_user = db.query(User).filter(User.uuid == user_uuid, User.deleted_at == None).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if target_user.role == UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot ban another Administrator.",
        )

    new_active_state = bool(body.get("is_active", False))
    reason = body.get("reason", "No reason provided")

    target_user.is_active = new_active_state
    target_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target_user)

    action_word = "unbanned" if new_active_state else "banned"
    logger.warning(
        f"Admin {current_user.uuid} {action_word} user {target_user.uuid}. Reason: {reason}"
    )

    return UserResponse.model_validate(target_user)


# ------------------------------------------------------------------------------
# 5. PUT /api/users/{uuid}/role (Change user role - Admin only)
# ------------------------------------------------------------------------------
@router.put("/{user_uuid}/role", response_model=UserResponse)
def change_user_role(
    user_uuid: UUID,
    body: Dict[str, Any],
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Change authorization role of a user. Restricted to Administrators."""
    role_raw = body.get("role")
    if not role_raw:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Role string is required in request body.",
        )

    try:
        new_role = UserRole(role_raw.lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role. Permitted roles: {[r.value for r in UserRole]}",
        )

    target_user = db.query(User).filter(User.uuid == user_uuid, User.deleted_at == None).first()
    if not target_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    if target_user.role == UserRole.ADMIN and target_user.id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify role of another Administrator.",
        )

    target_user.role = new_role
    target_user.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(target_user)

    logger.warning(
        f"Admin {current_user.uuid} changed role of user {target_user.uuid} to {new_role.value}"
    )

    return UserResponse.model_validate(target_user)


# ------------------------------------------------------------------------------
# 6. GET /api/users/{uuid}/issues (Issues reported by a specific user)
# ------------------------------------------------------------------------------
@router.get("/{user_uuid}/issues", response_model=IssueListResponse)
def get_user_reported_issues(
    user_uuid: UUID,
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
    status: Optional[IssueStatus] = Query(default=None, description="Filter by issue status"),
    db: Session = Depends(get_db),
):
    """Retrieve paginated issues submitted by a specific user."""
    user = db.query(User).filter(User.uuid == user_uuid, User.deleted_at == None).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    query = db.query(Issue).filter(Issue.reporter_id == user.id, Issue.deleted_at == None)

    if status:
        query = query.filter(Issue.status == status)

    query = query.order_by(desc(Issue.created_at))

    items, total, total_pages = paginate(query, page=page, page_size=page_size)
    summaries = [IssueSummary.model_validate(issue) for issue in items]

    return IssueListResponse(
        issues=summaries,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )

