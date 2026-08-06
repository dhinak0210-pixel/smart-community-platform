"""FastAPI Application Entry Point for Smart Community Platform."""

import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import check_db_connection, init_db, DATABASE_URL, _mask_database_url
from backend.routes import auth_router, users_router, issues_router, dashboard_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    logger.info("Initializing application startup sequence...")

    # 1. Check database connectivity
    if check_db_connection():
        logger.info("Database connection verified successfully.")
        init_db()
    else:
        logger.warning("Database connection failed on startup. Application operating in degraded mode.")

    # 2. Ensure uploads directory exists
    os.makedirs("uploads", exist_ok=True)
    yield
    logger.info("Application shutdown complete.")


app = FastAPI(
    title=settings.APP_NAME,
    description="A civic-tech platform connecting citizens with local authorities to report, track, and resolve community issues.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Configure CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount Static Files (Uploads & Frontend)
if os.path.exists("uploads"):
    app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")
if os.path.exists("frontend"):
    app.mount("/static", StaticFiles(directory="frontend"), name="frontend")

# Include API Routers under /api/v1 prefix
app.include_router(auth_router, prefix="/api/v1")
app.include_router(users_router, prefix="/api/v1")
app.include_router(issues_router, prefix="/api/v1")
app.include_router(dashboard_router, prefix="/api/v1")


@app.get("/", tags=["Health Check"])
@app.get("/health", tags=["Health Check"])
def health_check():
    """Health check endpoint returning API and database connection status."""
    db_connected = check_db_connection()
    return {
        "status": "healthy" if db_connected else "degraded",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "database": "connected" if db_connected else "disconnected",
        "database_url": _mask_database_url(DATABASE_URL),
        "docs": "/docs",
    }
