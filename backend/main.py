"""FastAPI Application Entry Point for Smart Community Platform."""

import os
import time
import logging
import asyncio
import re
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Dict, Any, List

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.orm import Session

from backend.config import settings
from backend.database import check_db_connection, init_db, DATABASE_URL, _mask_database_url
from backend.routes import (
    auth_router,
    users_router,
    issues_router,
    dashboard_router,
    volunteers_router,
    notifications_router,
    agents_router,
    upload_router,
)
from backend.routes.ai import router as ai_router
from backend.routes.websockets import router as websocket_router
from backend.ml.model_manager import model_manager
from backend.tasks.cleanup_tasks import run_temp_image_cleanup
from backend.agents.agent_scheduler import agent_scheduler

APP_START_TIME = time.time()


def setup_logging():
    log_level_str = getattr(settings, "LOG_LEVEL", "INFO")
    log_level = getattr(logging, str(log_level_str).upper(), logging.INFO)
    formatter = logging.Formatter(
        fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    if not root_logger.handlers:
        root_logger.addHandler(console_handler)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)
    logging.getLogger("ultralytics").setLevel(logging.WARNING)


setup_logging()
logger = logging.getLogger("smart_community")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan context manager for startup and shutdown events."""
    env_name = getattr(settings, "ENVIRONMENT", settings.APP_ENV)
    logger.info("=" * 50)
    logger.info("Smart Community Platform starting...")
    logger.info(f"Environment: {env_name}")
    logger.info(f"Debug mode: {settings.DEBUG}")
    logger.info("=" * 50)

    # 1. Non-blocking database connectivity check & table initialization
    async def _async_init_db():
        if await asyncio.to_thread(check_db_connection):
            logger.info("✅ Database connected successfully.")
            try:
                await asyncio.to_thread(init_db)
                logger.info("✅ Database tables verified.")
            except Exception as e:
                logger.error(f"Error during init_db: {e}")
        else:
            logger.warning("❌ Database connection failed on startup. Application operating in degraded mode.")

    asyncio.create_task(_async_init_db())


    # 2. Ensure essential directories exist
    try:
        os.makedirs("uploads", exist_ok=True)
        os.makedirs(settings.HUGGINGFACE_MODEL_CACHE_DIR, exist_ok=True)
    except Exception as e:
        logger.warning(f"Could not create local data directories: {e}")

    # 3. Non-blocking ML model loading & AI Agent Scheduler startup
    async def _async_init_services():
        if settings.APP_ENV != "testing":
            logger.info("Loading ML models in background...")
            try:
                results = await asyncio.to_thread(model_manager.load_all_models)
                loaded = sum(1 for v in results.values() if v)
                logger.info(f"✅ ML models: {loaded}/6 loaded")
            except Exception as e:
                logger.error(f"ML loading failed: {e}")
                logger.warning("Platform running with limited AI features")

            logger.info("Starting AI agents in background...")
            try:
                agent_scheduler.initialize()
                agent_scheduler.start()
                logger.info("✅ All agents started and scheduled")
            except Exception as e:
                logger.error(f"Agent startup failed: {e}")
                logger.warning("Platform running without automated agents")
        else:
            logger.info("APP_ENV=testing: Skipping heavy ML and Agent background startup.")

    asyncio.create_task(_async_init_services())


    # 5. Schedule background image cleanup tasks
    try:
        asyncio.create_task(run_temp_image_cleanup())
        logger.info("✅ Background cleanup task started")
    except Exception as e:
        logger.error(f"Cleanup task failed: {e}")

    route_paths = [getattr(r, "path", str(r)) for r in app.routes]
    logger.info(f"Registered {len(route_paths)} API route handlers.")

    logger.info("=" * 50)
    logger.info("✅ Smart Community Platform is READY")
    logger.info("   API docs: /docs")
    logger.info("   Health: /health")
    logger.info("=" * 50)

    yield

    try:
        agent_scheduler.shutdown()
        logger.info("AgentScheduler shut down successfully.")
    except Exception as e:
        logger.error(f"Error shutting down AgentScheduler: {e}")
    logger.info("Application shutdown sequence complete.")


app = FastAPI(
    title=settings.APP_NAME,
    description="A civic-tech platform connecting citizens with local authorities to report, track, and resolve community issues.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# 1. GZip Compression Middleware
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 2. CORS Middleware
cors_origins_list = [origin.strip() for origin in settings.CORS_ORIGINS.split(",") if origin.strip()] if isinstance(settings.CORS_ORIGINS, str) else settings.CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_list if cors_origins_list else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    max_age=86400,
)

# 3. Production Trusted Host Middleware
env_name = getattr(settings, "ENVIRONMENT", settings.APP_ENV)
if env_name == "production":
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            "*.onrender.com",
            "*.hf.space",
            "*.railway.app",
            "*.vercel.app",
            "localhost",
            "127.0.0.1",
            "*",
        ]
    )


# 4. Request Timing & Slow Request Logging Middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        if process_time > 1000:
            logger.warning(
                f"SLOW REQUEST: {request.method} {request.url.path} "
                f"took {process_time:.0f}ms status={response.status_code}"
            )
        response.headers["X-Process-Time"] = f"{process_time:.0f}ms"
        return response
    except Exception as e:
        process_time = (time.time() - start_time) * 1000
        logger.error(
            f"REQUEST FAILED: {request.method} {request.url.path} "
            f"error={str(e)} time={process_time:.0f}ms"
        )
        raise


# Global Custom Exception Handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    formatted_errors = []
    for err in errors:
        loc = " -> ".join([str(x) for x in err.get("loc", [])])
        msg = err.get("msg")
        formatted_errors.append(f"{loc}: {msg}")

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": "Validation Error",
            "errors": formatted_errors,
        },
    )


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled Server Exception on {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error occurred. Please try again later."},
    )


# Mount Routers under both /api & /api/v1
app.include_router(auth_router, prefix="/api/auth", tags=["Authentication"])
app.include_router(users_router, prefix="/api/users", tags=["Users"])
app.include_router(issues_router, prefix="/api", tags=["Issues"])
app.include_router(upload_router, prefix="/api/upload", tags=["Image Upload"])
app.include_router(agents_router)
app.include_router(ai_router)

app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication (v1)"])
app.include_router(users_router, prefix="/api/v1/users", tags=["Users (v1)"])
app.include_router(issues_router, prefix="/api/v1")
app.include_router(upload_router, prefix="/api/v1/upload", tags=["Image Upload (v1)"])
app.include_router(dashboard_router, prefix="/api/v1")
app.include_router(volunteers_router, prefix="/api/v1")
app.include_router(notifications_router, prefix="/api/v1")
app.include_router(agents_router, prefix="/api/v1")
app.include_router(websocket_router)


@app.get("/", tags=["Health Check"])
def root():
    """Basic application info endpoint."""
    return {
        "app": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "api_endpoints": "/api",
    }


@app.get("/health", tags=["Health Check"])
async def health_check():
    """Detailed system health check endpoint."""
    env_name = getattr(settings, "ENVIRONMENT", settings.APP_ENV)
    health = {
        "status": "healthy",
        "version": "1.0.0",
        "environment": env_name,
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int(time.time() - APP_START_TIME),
        "checks": {}
    }

    try:
        db_ok = await asyncio.wait_for(asyncio.to_thread(check_db_connection), timeout=0.8)
        health["checks"]["database"] = "connected" if db_ok else "disconnected"
        if not db_ok:
            health["status"] = "degraded"
    except asyncio.TimeoutError:
        health["checks"]["database"] = "connected (latency test timed out)"
    except Exception as e:
        health["checks"]["database"] = f"error: {str(e)[:50]}"
        health["status"] = "degraded"


    try:
        ml_status = model_manager.get_status()
        loaded = ml_status.get("total_loaded", 0)
        total = ml_status.get("total_models", 6)
        health["checks"]["ml_models"] = f"{loaded}/{total} loaded"
    except Exception:
        health["checks"]["ml_models"] = "not checked"

    try:
        agent_status = agent_scheduler.get_status()
        health["checks"]["agents"] = {
            "running": agent_status.get("scheduler_running", False),
            "count": agent_status.get("agents_registered", 0)
        }
    except Exception:
        health["checks"]["agents"] = "not started"

    if settings.DATABASE_URL:
        masked = re.sub(r"://[^@]+@", "://***@", settings.DATABASE_URL)
        health["checks"]["database_host"] = masked.split("@")[-1].split("/")[0]

    return health


@app.get("/api", tags=["API Discovery"])
def list_api_endpoints():
    """List all registered API endpoints."""
    endpoints = []
    for route in app.routes:
        if hasattr(route, "methods") and hasattr(route, "path"):
            endpoints.append({
                "path": route.path,
                "methods": list(route.methods),
                "name": route.name,
            })
    return {"total": len(endpoints), "endpoints": endpoints}


# Unified Local Hosting: Mount Uploads and Frontend Static Files
import os
from fastapi.staticfiles import StaticFiles

uploads_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "uploads")
try:
    os.makedirs(uploads_path, exist_ok=True)
except Exception:
    uploads_path = "/tmp/uploads"
    os.makedirs(uploads_path, exist_ok=True)

if os.path.exists(uploads_path):
    app.mount("/uploads", StaticFiles(directory=uploads_path), name="uploads")

frontend_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")
if os.path.exists(frontend_path):
    app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


