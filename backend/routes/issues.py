"""Issue CRUD, Search, Discussion, Voting, Map Markers, and Duplicate Detection Endpoints."""

import logging
import uuid as uuid_pkg
from datetime import datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query, File, UploadFile, BackgroundTasks
from sqlalchemy import func, select, or_, and_
from sqlalchemy.orm import Session, joinedload

from backend.database import get_db, SessionLocal
from backend.ml.pipeline import run_pipeline_background
from backend.models.user import User, UserRole
from backend.models.issue import (
    Issue,
    Vote,
    Comment,
    IssueHistory,
    IssueCategory,
    IssueStatus,
    IssuePriority,
    CommentType,
    VoteType,
    ChangeType,
)
from backend.schemas.issue import (
    IssueCreate,
    IssueUpdate,
    IssueStatusUpdate,
    IssuePriorityUpdate,
    IssueResolutionUpdate,
    CitizenResolutionConfirm,
    CommentCreate,
    VoteCreate,
    IssueSummary,
    IssueDetail,
    IssueListResponse,
    IssueMapMarker,
    IssueStatsResponse,
    CommentResponse,
    VoteResponse,
    IssueHistoryResponse,
)
from backend.schemas.user import UserPublicResponse
from backend.utils.upload import upload_issue_image, upload_temp_image, validate_image_file, move_temp_to_issue
from backend.utils.email import send_issue_status_update_email
from backend.utils.issue_helpers import (
    calculate_priority_score,
    detect_potential_duplicates,
    generate_issue_tags,
    get_issue_statistics,
    find_nearby_issues,
)
from backend.ml.categorizer import categorize_text
from backend.utils.auth import get_current_user, require_role

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/issues", tags=["Issues"])


# ------------------------------------------------------------------------------
# Helper Converters
# ------------------------------------------------------------------------------
def to_user_public(user: Optional[User]) -> Optional[UserPublicResponse]:
    """Convert User ORM model to UserPublicResponse schema."""
    if not user:
        return None
    return UserPublicResponse.model_validate(user)


def format_comment_response(comment: Comment) -> CommentResponse:
    """Recursively convert Comment ORM model into CommentResponse schema."""
    replies_formatted = [
        format_comment_response(reply)
        for reply in comment.replies
        if reply.deleted_at is None
    ]
    return CommentResponse(
        uuid=comment.uuid,
        content=comment.content,
        comment_type=comment.comment_type,
        is_pinned=comment.is_pinned,
        is_edited=comment.is_edited,
        like_count=comment.like_count,
        user=to_user_public(comment.user),
        replies=replies_formatted,
        created_at=comment.created_at,
        edited_at=comment.edited_at,
    )


def format_issue_detail(issue: Issue, db: Session) -> IssueDetail:
    """Format full Issue ORM model into IssueDetail response schema."""
    # Top-level comments with replies
    top_comments = (
        db.query(Comment)
        .options(joinedload(Comment.user), joinedload(Comment.replies))
        .filter(Comment.issue_id == issue.id, Comment.parent_id == None, Comment.deleted_at == None)
        .order_by(Comment.is_pinned.desc(), Comment.created_at.asc())
        .all()
    )
    formatted_comments = [format_comment_response(c) for c in top_comments]

    # Audit history log
    history_entries = (
        db.query(IssueHistory)
        .options(joinedload(IssueHistory.user))
        .filter(IssueHistory.issue_id == issue.id)
        .order_by(IssueHistory.created_at.desc())
        .all()
    )
    formatted_history = [
        IssueHistoryResponse(
            uuid=h.uuid,
            change_type=h.change_type,
            old_value=h.old_value,
            new_value=h.new_value,
            note=h.note,
            changed_by=to_user_public(h.user),
            created_at=h.created_at,
        )
        for h in history_entries
    ]

    short_desc = issue.short_description or (
        (issue.description[:147] + "...") if len(issue.description) > 150 else issue.description
    )

    image_list = issue.image_urls if issue.image_urls else ([issue.image_url] if issue.image_url else [])

    return IssueDetail(
        id=issue.id,
        uuid=issue.uuid,
        title=issue.title,
        description=issue.description,
        short_description=short_desc,
        category=issue.category,
        status=issue.status,
        priority=issue.priority,
        location_lat=issue.location_lat,
        location_lng=issue.location_lng,
        location_address=issue.location_address,
        location_city=issue.location_city,
        location_area=issue.location_area,
        location_landmark=issue.location_landmark,
        image_url=issue.image_url,
        image_urls=image_list,
        ai_suggested_category=issue.ai_suggested_category,
        ai_category_confidence=issue.ai_category_confidence,
        ai_tags=issue.ai_tags or [],
        ai_image_analysis=issue.ai_image_analysis,
        assigned_to=to_user_public(issue.assigned_to),
        assigned_department=issue.assigned_department,
        status_note=issue.status_note,
        resolution_note=issue.resolution_note,
        resolved_at=issue.resolved_at,
        vote_count=issue.vote_count or 0,
        comment_count=issue.comment_count or 0,
        view_count=issue.view_count or 0,
        days_open=issue.days_open(),
        reported_by=to_user_public(issue.reporter),
        history=formatted_history,
        comments=formatted_comments,
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


def format_issue_summary(issue: Issue) -> IssueSummary:
    """Format Issue ORM model into lightweight IssueSummary response schema."""
    short_desc = issue.short_description or (
        (issue.description[:147] + "...") if len(issue.description) > 150 else issue.description
    )
    return IssueSummary(
        id=issue.id,
        uuid=issue.uuid,
        title=issue.title,
        short_description=short_desc,
        category=issue.category,
        status=issue.status,
        priority=issue.priority,
        location_address=issue.location_address,
        location_city=issue.location_city,
        image_url=issue.image_url,
        vote_count=issue.vote_count or 0,
        comment_count=issue.comment_count or 0,
        view_count=issue.view_count or 0,
        days_open=issue.days_open(),
        reported_by=to_user_public(issue.reporter),
        created_at=issue.created_at,
        updated_at=issue.updated_at,
    )


# ------------------------------------------------------------------------------
# API Endpoints
# ------------------------------------------------------------------------------
@router.post("/auto-categorize", response_model=dict)
def auto_categorize_issue(payload: dict):
    """Predict issue category from title and description text."""
    title = payload.get("title", "")
    description = payload.get("description", "")
    predicted_category = categorize_text(title, description)
    return {"predicted_category": predicted_category.value}


@router.post("/upload", response_model=dict)
async def upload_issue_image_endpoint(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user)
):
    """Upload an image photo for an issue report (temp upload)."""
    res = await upload_temp_image(file, session_id=str(current_user.uuid))
    return {
        "url": res["url"],
        "image_url": res["url"],
        "temp_id": res["temp_id"],
        "public_id": res.get("public_id", res["temp_id"]),
        "thumbnail_url": res["thumbnail_url"]
    }



@router.post("/{issue_uuid}/images", response_model=IssueDetail)
async def add_image_to_issue(
    issue_uuid: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Upload and attach an image photo to an existing issue."""
    try:
        parsed_uuid = uuid_pkg.UUID(issue_uuid)
        issue = db.execute(select(Issue).where(Issue.uuid == parsed_uuid, Issue.deleted_at == None)).scalar_one_or_none()
    except ValueError:
        issue = None

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    image_list = list(issue.image_urls or [])
    if len(image_list) >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum limit of 5 images reached for this issue."
        )

    is_primary = (len(image_list) == 0)
    upload_res = await upload_issue_image(
        file=file,
        issue_uuid=str(issue.uuid),
        image_index=len(image_list),
        is_primary=is_primary
    )

    image_list.append(upload_res["url"])
    issue.image_urls = image_list
    if is_primary or not issue.image_url:
        issue.image_url = upload_res["url"]

    db.commit()
    db.refresh(issue)
    return format_issue_detail(issue, db)


@router.post("/duplicate-check", response_model=dict)
def check_duplicate_issues(
    payload: dict,
    db: Session = Depends(get_db)
):
    """Check for potential duplicate issues within 200m radius."""
    title = payload.get("title", "")
    description = payload.get("description", "")
    lat = float(payload.get("location_lat", 0.0))
    lng = float(payload.get("location_lng", 0.0))
    category = payload.get("category", "other")

    duplicates = detect_potential_duplicates(
        db=db,
        title=title,
        description=description,
        lat=lat,
        lng=lng,
        category=category,
    )
    return {"potential_duplicates": duplicates, "count": len(duplicates)}


@router.get("/map", response_model=List[IssueMapMarker])
def get_map_markers(
    category: Optional[IssueCategory] = None,
    status: Optional[IssueStatus] = None,
    city: Optional[str] = None,
    sw_lat: Optional[float] = None,
    sw_lng: Optional[float] = None,
    ne_lat: Optional[float] = None,
    ne_lng: Optional[float] = None,
    db: Session = Depends(get_db)
):
    """Retrieve compact map marker payload for GIS map views."""
    query = db.query(Issue).filter(Issue.deleted_at == None)

    if category:
        query = query.filter(Issue.category == category)
    if status:
        query = query.filter(Issue.status == status)
    if city:
        query = query.filter(Issue.location_city.ilike(f"%{city}%"))

    if sw_lat is not None and ne_lat is not None:
        query = query.filter(Issue.location_lat.between(sw_lat, ne_lat))
    if sw_lng is not None and ne_lng is not None:
        query = query.filter(Issue.location_lng.between(sw_lng, ne_lng))

    issues = query.all()
    return [
        IssueMapMarker(
            uuid=issue.uuid,
            title=issue.title,
            status=issue.status,
            priority=issue.priority,
            category=issue.category,
            location_lat=issue.location_lat,
            location_lng=issue.location_lng,
            vote_count=issue.vote_count or 0,
            created_at=issue.created_at,
        )
        for issue in issues
    ]


@router.get("/stats", response_model=IssueStatsResponse)
def get_platform_issue_stats(db: Session = Depends(get_db)):
    """Retrieve aggregate issue statistics and performance metrics."""
    stats_data = get_issue_statistics(db)
    return IssueStatsResponse(**stats_data)


@router.get("/", response_model=IssueListResponse)
def list_issues(
    category: Optional[IssueCategory] = None,
    status: Optional[IssueStatus] = None,
    priority: Optional[IssuePriority] = None,
    city: Optional[str] = None,
    area: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query(default="created_at", pattern="^(created_at|vote_count|priority|updated_at)$"),
    sort_order: str = Query(default="desc", pattern="^(asc|desc)$"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db)
):
    """Retrieve paginated community issues with dynamic filtering and sorting."""
    query = db.query(Issue).options(joinedload(Issue.reported_by)).filter(Issue.deleted_at == None)

    if category:
        query = query.filter(Issue.category == category)
    if status:
        query = query.filter(Issue.status == status)
    if priority:
        query = query.filter(Issue.priority == priority)
    if city:
        query = query.filter(Issue.location_city.ilike(f"%{city}%"))
    if area:
        query = query.filter(Issue.location_area.ilike(f"%{area}%"))
    if search:
        search_fmt = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Issue.title.ilike(search_fmt),
                Issue.description.ilike(search_fmt),
                Issue.location_address.ilike(search_fmt),
            )
        )

    total_count = query.count()
    total_pages = (total_count + page_size - 1) // page_size if total_count > 0 else 1

    # Sorting
    sort_attr = getattr(Issue, sort_by, Issue.created_at)
    if sort_order == "desc":
        query = query.order_by(sort_attr.desc())
    else:
        query = query.order_by(sort_attr.asc())

    skip = (page - 1) * page_size
    issues = query.offset(skip).limit(page_size).all()

    summaries = [format_issue_summary(issue) for issue in issues]

    return IssueListResponse(
        issues=summaries,
        total=total_count,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
        filters_applied={
            "category": category.value if category else None,
            "status": status.value if status else None,
            "priority": priority.value if priority else None,
            "city": city,
            "area": area,
            "search": search,
            "sort_by": sort_by,
            "sort_order": sort_order,
        },
    )


@router.post("/", response_model=IssueDetail, status_code=status.HTTP_201_CREATED)
def create_issue(
    issue_in: IssueCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Report a new community issue."""
    assigned_category = issue_in.category
    if not assigned_category or assigned_category == IssueCategory.OTHER:
        assigned_category = categorize_text(issue_in.title, issue_in.description)

    extracted_tags = generate_issue_tags(issue_in.title, issue_in.description)
    short_desc = (
        issue_in.description[:147] + "..." if len(issue_in.description) > 150 else issue_in.description
    )

    new_issue = Issue(
        title=issue_in.title,
        description=issue_in.description,
        short_description=short_desc,
        category=assigned_category,
        priority=issue_in.priority or IssuePriority.MEDIUM,
        status=IssueStatus.REPORTED,
        location_lat=issue_in.location_lat,
        location_lng=issue_in.location_lng,
        location_address=issue_in.location_address,
        location_city=issue_in.location_city,
        location_area=issue_in.location_area,
        location_landmark=issue_in.location_landmark,
        ai_tags=extracted_tags,
        reporter_id=current_user.id,
    )

    init_image_url = issue_in.image_url
    if issue_in.temp_id:
        try:
            promoted = move_temp_to_issue(temp_public_id=issue_in.temp_id, issue_uuid=str(new_issue.uuid), image_index=0)
            init_image_url = promoted.get("url", init_image_url)
        except Exception as e:
            logger.warning(f"Could not promote temp image '{issue_in.temp_id}': {e}")

    if init_image_url:
        new_issue.image_url = init_image_url
        new_issue.image_urls = [init_image_url]

    # Automated AI Triage via ReporterAgent
    try:
        from backend.agents import ReporterAgent
        reporter_agent = ReporterAgent()
        triage_res = reporter_agent.analyze_report(
            title=new_issue.title,
            description=new_issue.description,
            category=assigned_category.value if hasattr(assigned_category, 'value') else str(assigned_category)
        )
        if triage_res.get("recommended_priority"):
            rec_prio = triage_res["recommended_priority"].upper()
            if hasattr(IssuePriority, rec_prio):
                new_issue.priority = getattr(IssuePriority, rec_prio)

        ai_kws = triage_res.get("detected_keywords", [])
        combined_tags = list(set(extracted_tags + ai_kws))
        new_issue.ai_tags = combined_tags
        new_issue.ai_suggested_category = assigned_category.value if hasattr(assigned_category, 'value') else str(assigned_category)
        new_issue.ai_category_confidence = 0.90 if triage_res.get("urgency_score") else 0.75
    except Exception as err:
        logger.warning(f"AI Triage during issue creation failed: {err}")

    db.add(new_issue)
    db.flush()

    # Update user reported issues count & reputation
    current_user.total_issues_reported = (current_user.total_issues_reported or 0) + 1
    current_user.add_reputation(5, reason="Reported new community issue")

    # Initial history log
    initial_history = IssueHistory(
        issue_id=new_issue.id,
        changed_by_id=current_user.id,
        change_type=ChangeType.STATUS_CHANGE,
        old_value=None,
        new_value=IssueStatus.REPORTED.value,
        note="Issue report created with AI triage.",
    )
    db.add(initial_history)

    db.commit()
    db.refresh(new_issue)

    # Queue full background AI pipeline task
    cat_val = assigned_category.value if hasattr(assigned_category, 'value') else str(assigned_category)
    background_tasks.add_task(
        run_pipeline_background,
        issue_uuid=str(new_issue.uuid),
        title=new_issue.title,
        description=new_issue.description,
        lat=new_issue.location_lat,
        lng=new_issue.location_lng,
        location_city=new_issue.location_city,
        category=cat_val,
        image_url=new_issue.image_url,
        db_session_factory=SessionLocal
    )

    logger.info(f"New issue created: '{new_issue.title}' (UUID: {new_issue.uuid}) by user {current_user.email}")
    return format_issue_detail(new_issue, db)


@router.get("/{issue_uuid}", response_model=IssueDetail)
def get_issue(issue_uuid: uuid_pkg.UUID, db: Session = Depends(get_db)):
    """Get details of a specific issue by public UUID."""
    issue = (
        db.query(Issue)
        .options(joinedload(Issue.reported_by), joinedload(Issue.assigned_to))
        .filter(Issue.uuid == issue_uuid, Issue.deleted_at == None)
        .first()
    )

    if not issue:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Issue with UUID {issue_uuid} not found."
        )

    # Increment view count atomically
    issue.view_count = (issue.view_count or 0) + 1
    db.commit()

    return format_issue_detail(issue, db)


@router.put("/{issue_uuid}", response_model=IssueDetail)
def update_issue(
    issue_uuid: uuid_pkg.UUID,
    issue_in: IssueUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update issue details by reporter or admin."""
    issue = db.query(Issue).filter(Issue.uuid == issue_uuid, Issue.deleted_at == None).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    if issue.reporter_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the original reporter or an admin can edit issue details."
        )

    changes = issue_in.model_dump(exclude_unset=True)
    for field, new_val in changes.items():
        old_val = getattr(issue, field, None)
        if old_val != new_val:
            setattr(issue, field, new_val)
            history = IssueHistory(
                issue_id=issue.id,
                changed_by_id=current_user.id,
                change_type=ChangeType.DETAILS_EDIT,
                old_value=str(old_val),
                new_value=str(new_val),
                note=f"Field '{field}' updated.",
            )
            db.add(history)

    db.commit()
    db.refresh(issue)
    return format_issue_detail(issue, db)


@router.patch("/{issue_uuid}/status", response_model=IssueDetail)
def update_issue_status(
    issue_uuid: uuid_pkg.UUID,
    status_in: IssueStatusUpdate,
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Update issue status and assignment (Authorities & Admins only)."""
    issue = (
        db.query(Issue)
        .options(joinedload(Issue.reported_by))
        .filter(Issue.uuid == issue_uuid, Issue.deleted_at == None)
        .first()
    )

    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    old_status = issue.status.value if hasattr(issue.status, 'value') else str(issue.status)
    new_status = status_in.status.value if hasattr(status_in.status, 'value') else str(status_in.status)

    if old_status != new_status:
        issue.status = status_in.status
        issue.status_note = status_in.status_note

        if status_in.status == IssueStatus.REJECTED:
            issue.rejection_reason = status_in.rejection_reason

        if status_in.status == IssueStatus.RESOLVED:
            issue.resolved_at = datetime.utcnow()

        history = IssueHistory(
            issue_id=issue.id,
            changed_by_id=current_user.id,
            change_type=ChangeType.STATUS_CHANGE,
            old_value=old_status,
            new_value=new_status,
            note=status_in.status_note or f"Status updated to {new_status}",
        )
        db.add(history)

    if status_in.assigned_to is not None:
        assigned_user = db.query(User).filter(User.id == status_in.assigned_to, User.deleted_at == None).first()
        if assigned_user:
            issue.assigned_to_id = assigned_user.id

    if status_in.assigned_department is not None:
        issue.assigned_department = status_in.assigned_department

    db.commit()
    db.refresh(issue)

    # Dispatch status update email notification to original reporter if applicable
    if issue.reporter and issue.reporter.email:
        send_issue_status_update_email(
            to_email=issue.reporter.email,
            user_name=issue.reporter.name,
            issue_title=issue.title,
            issue_uuid=str(issue.uuid),
            old_status=old_status,
            new_status=new_status,
            status_note=status_in.status_note,
        )

    return format_issue_detail(issue, db)


@router.patch("/{issue_uuid}/priority", response_model=IssueDetail)
def update_issue_priority(
    issue_uuid: uuid_pkg.UUID,
    priority_in: IssuePriorityUpdate,
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Override issue priority (Authorities & Admins only)."""
    issue = db.query(Issue).filter(Issue.uuid == issue_uuid, Issue.deleted_at == None).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    old_pri = issue.priority.value if hasattr(issue.priority, 'value') else str(issue.priority)
    new_pri = priority_in.priority.value if hasattr(priority_in.priority, 'value') else str(priority_in.priority)

    if old_pri != new_pri:
        issue.priority = priority_in.priority
        history = IssueHistory(
            issue_id=issue.id,
            changed_by_id=current_user.id,
            change_type=ChangeType.PRIORITY_CHANGE,
            old_value=old_pri,
            new_value=new_pri,
            note=priority_in.reason or f"Priority changed to {new_pri}",
        )
        db.add(history)
        db.commit()
        db.refresh(issue)

    return format_issue_detail(issue, db)


@router.patch("/{issue_uuid}/resolution", response_model=IssueDetail)
def submit_issue_resolution(
    issue_uuid: uuid_pkg.UUID,
    resolution_in: IssueResolutionUpdate,
    current_user: User = Depends(require_role(UserRole.AUTHORITY, UserRole.ADMIN)),
    db: Session = Depends(get_db)
):
    """Submit official resolution notes (Authorities & Admins only)."""
    issue = db.query(Issue).filter(Issue.uuid == issue_uuid, Issue.deleted_at == None).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    issue.status = IssueStatus.RESOLVED
    issue.resolution_note = resolution_in.resolution_note
    if resolution_in.resolved_by_department:
        issue.assigned_department = resolution_in.resolved_by_department
    issue.resolved_at = datetime.utcnow()

    history = IssueHistory(
        issue_id=issue.id,
        changed_by_id=current_user.id,
        change_type=ChangeType.STATUS_CHANGE,
        old_value=issue.status.value,
        new_value=IssueStatus.RESOLVED.value,
        note=f"Resolution summary: {resolution_in.resolution_note[:100]}...",
    )
    db.add(history)
    db.commit()
    db.refresh(issue)

    return format_issue_detail(issue, db)


@router.post("/{issue_uuid}/confirm", response_model=IssueDetail)
def confirm_issue_resolution(
    issue_uuid: uuid_pkg.UUID,
    confirm_in: CitizenResolutionConfirm,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Citizen confirms or rejects resolution status of their reported issue."""
    issue = db.query(Issue).filter(Issue.uuid == issue_uuid, Issue.deleted_at == None).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    if issue.reporter_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the original reporter can confirm resolution satisfaction."
        )

    issue.citizen_confirmed_resolved = confirm_in.confirmed
    issue.resolution_rating = confirm_in.rating
    issue.resolution_feedback = confirm_in.feedback

    if confirm_in.confirmed:
        current_user.add_reputation(15, reason="Confirmed issue resolution")
        if issue.reporter:
            issue.reporter.total_issues_resolved = (issue.reporter.total_issues_resolved or 0) + 1

    db.commit()
    db.refresh(issue)

    return format_issue_detail(issue, db)


@router.post("/{issue_uuid}/vote", response_model=VoteResponse)
def vote_issue(
    issue_uuid: uuid_pkg.UUID,
    vote_in: VoteCreate = VoteCreate(),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Cast an upvote on an issue or toggle off if already voted."""
    issue = (
        db.query(Issue)
        .options(joinedload(Issue.reported_by))
        .filter(Issue.uuid == issue_uuid, Issue.deleted_at == None)
        .first()
    )
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    existing_vote = db.query(Vote).filter(
        Vote.issue_id == issue.id,
        Vote.user_id == current_user.id
    ).first()

    if existing_vote:
        # Toggle vote off
        db.delete(existing_vote)
        issue.vote_count = max(0, (issue.vote_count or 1) - 1)
        current_user.total_votes_given = max(0, (current_user.total_votes_given or 1) - 1)
        if issue.reporter:
            issue.reporter.add_reputation(-2, reason="Upvote removed from reported issue")

        db.commit()
        raise HTTPException(status_code=status.HTTP_200_OK, detail="Vote removed successfully.")

    # Cast new upvote
    new_vote = Vote(
        issue_id=issue.id,
        user_id=current_user.id,
        vote_type=vote_in.vote_type or VoteType.UPVOTE,
    )
    db.add(new_vote)

    issue.vote_count = (issue.vote_count or 0) + 1
    current_user.total_votes_given = (current_user.total_votes_given or 0) + 1
    if issue.reporter:
        issue.reporter.add_reputation(2, reason="Upvote received on reported issue")

    db.commit()

    return VoteResponse(
        issue_uuid=issue.uuid,
        vote_type=new_vote.vote_type,
        user=to_user_public(current_user),
        created_at=new_vote.created_at,
    )


@router.post("/{issue_uuid}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
def add_comment(
    issue_uuid: uuid_pkg.UUID,
    comment_in: CommentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Add a discussion comment or threaded reply to an issue."""
    issue = db.query(Issue).filter(Issue.uuid == issue_uuid, Issue.deleted_at == None).first()
    if not issue:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Issue not found.")

    parent_id = None
    if comment_in.parent_id:
        parent_comment = db.query(Comment).filter(
            Comment.id == comment_in.parent_id,
            Comment.issue_id == issue.id,
            Comment.deleted_at == None
        ).first()
        if not parent_comment:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent comment not found.")
        parent_id = parent_comment.id

    comment_type = comment_in.comment_type or CommentType.CITIZEN_COMMENT
    if current_user.role in [UserRole.AUTHORITY, UserRole.ADMIN]:
        comment_type = CommentType.AUTHORITY_UPDATE

    new_comment = Comment(
        issue_id=issue.id,
        user_id=current_user.id,
        parent_id=parent_id,
        content=comment_in.content,
        comment_type=comment_type,
    )
    db.add(new_comment)

    issue.comment_count = (issue.comment_count or 0) + 1
    current_user.total_comments = (current_user.total_comments or 0) + 1
    current_user.add_reputation(1, reason="Posted issue comment")

    db.commit()
    db.refresh(new_comment)

    return format_comment_response(new_comment)


@router.delete("/{issue_uuid}/comments/{comment_uuid}")
def delete_comment(
    issue_uuid: uuid_pkg.UUID,
    comment_uuid: uuid_pkg.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Soft delete a comment (Author or Admin only)."""
    comment = db.query(Comment).filter(Comment.uuid == comment_uuid, Comment.deleted_at == None).first()
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found.")

    if comment.user_id != current_user.id and current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this comment.")

    comment.deleted_at = datetime.utcnow()

    issue = db.query(Issue).filter(Issue.id == comment.issue_id).first()
    if issue:
        issue.comment_count = max(0, (issue.comment_count or 1) - 1)

    db.commit()
    return {"message": "Comment deleted successfully."}
