"""API route handlers package."""

from backend.routes.auth import router as auth_router
from backend.routes.users import router as users_router
from backend.routes.issues import router as issues_router
from backend.routes.dashboard import router as dashboard_router

__all__ = [
    "auth_router",
    "users_router",
    "issues_router",
    "dashboard_router",
]
