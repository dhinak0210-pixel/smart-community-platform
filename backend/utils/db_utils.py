"""Database utility helpers for pagination, multi-field search, dynamic filtering, sorting, and transaction handling.

Supports SQLAlchemy 2.0 modern select() query objects.
"""

import logging
import math
from contextlib import contextmanager
from typing import Generator, List, Dict, Any, Optional, Type
from sqlalchemy import select, func, or_, asc, desc
from sqlalchemy.sql import Select
from sqlalchemy.orm import Session, DeclarativeBase

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------------------
# 1. Pagination Helper
# ------------------------------------------------------------------------------
def paginate(
    query: Select,
    db: Session,
    page: int = 1,
    page_size: int = 20,
) -> Dict[str, Any]:
    """Paginate a SQLAlchemy 2.0 Select query.

    Args:
        query (Select): Base SQLAlchemy select() statement.
        db (Session): Active database session.
        page (int): Current page number (1-indexed). Defaults to 1.
        page_size (int): Number of items per page. Max 100, default 20.

    Returns:
        Dict[str, Any]: Dictionary containing items, total_count, total_pages, and current_page.

    Example:
        >>> stmt = select(Issue)
        >>> result = paginate(stmt, db, page=1, page_size=10)
        >>> print(result["items"], result["total_count"])
    """
    # Enforce safe limits
    page = max(1, page)
    page_size = min(100, max(1, page_size))

    # Count total matching rows
    count_stmt = select(func.count()).select_from(query.subquery())
    total_count: int = db.execute(count_stmt).scalar() or 0

    # Calculate total pages
    total_pages: int = math.ceil(total_count / page_size) if total_count > 0 else 1
    offset: int = (page - 1) * page_size

    # Execute paginated query
    paginated_stmt = query.offset(offset).limit(page_size)
    items = db.execute(paginated_stmt).scalars().all()

    return {
        "items": list(items),
        "total_count": total_count,
        "total_pages": total_pages,
        "current_page": page,
        "page_size": page_size,
    }


# ------------------------------------------------------------------------------
# 2. Multi-Field Search Helper
# ------------------------------------------------------------------------------
def apply_search(
    query: Select,
    model: Type[DeclarativeBase],
    search_term: Optional[str],
    fields: List[str],
) -> Select:
    """Apply case-insensitive multi-field ILIKE search to a query.

    Args:
        query (Select): Base select() statement.
        model (Type[DeclarativeBase]): Target SQLAlchemy model.
        search_term (Optional[str]): Search keyword.
        fields (List[str]): Model field names to search across.

    Returns:
        Select: Filtered select() statement.

    Example:
        >>> stmt = select(Issue)
        >>> stmt = apply_search(stmt, Issue, "pothole", ["title", "description"])
    """
    if not search_term or not fields:
        return query

    search_pattern = f"%{search_term.strip()}%"
    conditions = []

    for field_name in fields:
        if hasattr(model, field_name):
            field_attr = getattr(model, field_name)
            conditions.append(field_attr.ilike(search_pattern))

    if conditions:
        return query.where(or_(*conditions))

    return query


# ------------------------------------------------------------------------------
# 3. Dynamic Filter Helper
# ------------------------------------------------------------------------------
def apply_filters(
    query: Select,
    model: Type[DeclarativeBase],
    filters_dict: Dict[str, Any],
) -> Select:
    """Apply dynamic dictionary equality and date-range filters to a query.

    Ignores keys with None values.
    Supports date range keys ending in '_gte' and '_lte'.

    Args:
        query (Select): Base select() statement.
        model (Type[DeclarativeBase]): Target SQLAlchemy model.
        filters_dict (Dict[str, Any]): Dictionary of field -> value criteria.

    Returns:
        Select: Filtered select() statement.

    Example:
        >>> stmt = select(Issue)
        >>> stmt = apply_filters(stmt, Issue, {"status": "reported", "category": None})
    """
    if not filters_dict:
        return query

    for key, value in filters_dict.items():
        if value is None:
            continue

        # Handle date range suffix filters (e.g. created_at_gte)
        if key.endswith("_gte"):
            field_name = key[:-4]
            if hasattr(model, field_name):
                query = query.where(getattr(model, field_name) >= value)
        elif key.endswith("_lte"):
            field_name = key[:-4]
            if hasattr(model, field_name):
                query = query.where(getattr(model, field_name) <= value)
        elif hasattr(model, key):
            field_attr = getattr(model, key)
            val_cmp = value.value if hasattr(value, "value") else value
            query = query.where(field_attr == val_cmp)

    return query


# ------------------------------------------------------------------------------
# 4. Sorting Helper
# ------------------------------------------------------------------------------
def apply_sort(
    query: Select,
    model: Type[DeclarativeBase],
    sort_by: str = "created_at",
    sort_order: str = "desc",
) -> Select:
    """Apply sorting criteria to a query safely.

    Args:
        query (Select): Base select() statement.
        model (Type[DeclarativeBase]): Target SQLAlchemy model.
        sort_by (str): Field name to sort by. Defaults to 'created_at'.
        sort_order (str): 'asc' or 'desc'. Defaults to 'desc'.

    Returns:
        Select: Sorted select() statement.

    Example:
        >>> stmt = select(Issue)
        >>> stmt = apply_sort(stmt, Issue, sort_by="priority", sort_order="desc")
    """
    if not hasattr(model, sort_by):
        # Fallback to created_at if requested sort_by doesn't exist
        if hasattr(model, "created_at"):
            sort_by = "created_at"
        elif hasattr(model, "id"):
            sort_by = "id"
        else:
            return query

    field_attr = getattr(model, sort_by)
    direction = desc if sort_order.lower() == "desc" else asc

    return query.order_by(direction(field_attr))


# ------------------------------------------------------------------------------
# 5. Transaction Context Manager
# ------------------------------------------------------------------------------
@contextmanager
def with_transaction(db: Session) -> Generator[Session, None, None]:
    """Context manager for executing multiple database operations inside a single transaction.

    Automatically commits on success, and rolls back on exception.

    Args:
        db (Session): Active database session.

    Yields:
        Session: The active database session.

    Example:
        >>> with with_transaction(db):
        ...     db.add(new_user)
        ...     db.add(new_issue)
    """
    try:
        yield db
        db.commit()
        logger.debug("Transaction committed successfully.")
    except Exception as e:
        logger.error(f"Transaction failed, rolling back: {e}")
        db.rollback()
        raise
