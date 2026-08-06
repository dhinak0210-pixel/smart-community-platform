"""API routers package for Smart Community Platform."""

from backend.routes.auth import router as auth_router
from backend.routes.users import router as users_router
from backend.routes.issues import router as issues_router
from backend.routes.dashboard import router as dashboard_router
from backend.routes.volunteers import router as volunteers_router
from backend.routes.notifications import router as notifications_router
from backend.routes.agents import router as agents_router

__all__ = [
    "auth_router",
    "users_router",
    "issues_router",
    "dashboard_router",
    "volunteers_router",
    "notifications_router",
    "agents_router",
]
