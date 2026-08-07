"""Automated unit tests for backend/utils/db_utils.py pagination, filter, search, sort, and transaction helpers."""

from sqlalchemy import select
from backend.models.user import User, UserRole
from backend.models.issue import Issue, IssueCategory, IssueStatus, IssuePriority
from backend.utils.db_utils import paginate, apply_search, apply_filters, apply_sort, with_transaction


def test_db_utils_pagination_and_helpers(db_session):
    """Test db_utils pagination, ILIKE search, filtering, and sorting."""
    # Seed test user
    user = User(
        email="testdbuser@example.com",
        password_hash="hashedpassword",
        name="DB Test User",
        role=UserRole.CITIZEN
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    # Seed test issues
    issue1 = Issue(
        title="Major Pothole on Highway",
        description="Dangerous crater in lane 2 requiring urgent asphalt",
        category=IssueCategory.INFRASTRUCTURE,
        status=IssueStatus.REPORTED,
        priority=IssuePriority.CRITICAL,
        location_lat=13.08,
        location_lng=80.27,
        reporter_id=user.id
    )
    issue2 = Issue(
        title="Flickering Light in Sector 5",
        description="Lamp post bulb is unlit at night",
        category=IssueCategory.UTILITIES,
        status=IssueStatus.IN_PROGRESS,
        priority=IssuePriority.LOW,
        location_lat=13.09,
        location_lng=80.28,
        reporter_id=user.id
    )
    db_session.add_all([issue1, issue2])
    db_session.commit()

    # 1. Test Search
    search_stmt = select(Issue)
    search_stmt = apply_search(search_stmt, Issue, "Pothole", ["title", "description"])
    search_results = db_session.execute(search_stmt).scalars().all()
    assert len(search_results) == 1
    assert search_results[0].id == issue1.id

    # 2. Test Filters
    filter_stmt = select(Issue)
    filter_stmt = apply_filters(filter_stmt, Issue, {"status": IssueStatus.IN_PROGRESS})
    filter_results = db_session.execute(filter_stmt).scalars().all()
    assert len(filter_results) == 1
    assert filter_results[0].id == issue2.id

    # 3. Test Sorting
    sort_stmt = select(Issue)
    sort_stmt = apply_sort(sort_stmt, Issue, sort_by="title", sort_order="asc")
    sort_results = db_session.execute(sort_stmt).scalars().all()
    assert sort_results[0].title.startswith("Flickering")

    # 4. Test Paginate
    stmt = select(Issue)
    page_data = paginate(stmt, db_session, page=1, page_size=1)
    assert page_data["total_count"] == 2
    assert page_data["total_pages"] == 2
    assert len(page_data["items"]) == 1

    # 5. Test Transaction Context Manager
    with with_transaction(db_session):
        new_issue = Issue(
            title="Burst Water Main",
            description="Water leaking across sidewalk",
            category=IssueCategory.FLOODING,
            location_lat=13.10,
            location_lng=80.29,
            reporter_id=user.id
        )
        db_session.add(new_issue)

    count = db_session.execute(select(Issue)).scalars().all()
    assert len(count) == 3
