"""FastAPI Application Entry Point for Smart Community Platform."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.database import engine, Base
from backend.routes import auth_router, users_router, issues_router, dashboard_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    # Ensure database tables exist on startup if database is reachable
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"Startup DB warning: Could not initialize database tables: {e}")
    # Ensure uploads directory exists
    os.makedirs("uploads", exist_ok=True)
    yield


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
def root_health_check():
    """Health check endpoint returning API status."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "environment": settings.APP_ENV,
        "docs": "/docs",
    }
