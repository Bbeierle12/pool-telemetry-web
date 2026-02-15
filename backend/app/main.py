"""FastAPI application entry point."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.database import init_db, close_db
from app.core.rate_limit import limiter
from app.api.routes import sessions, video, events, export, auth, analysis, coaching, settings as settings_routes
from app.api.websockets import events as ws_events, video as ws_video

# Ensure data directories exist before app starts
settings.data_directory.mkdir(parents=True, exist_ok=True)
(settings.data_directory / "sessions").mkdir(exist_ok=True)
(settings.data_directory / "uploads").mkdir(exist_ok=True)
(settings.data_directory / "hls").mkdir(exist_ok=True)
(settings.data_directory / "exports").mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    await init_db()

    yield

    # Shutdown
    await close_db()


app = FastAPI(
    title=settings.app_name,
    description="Pool/Billiards Telemetry Recording and Analysis",
    version="2.0.0",
    lifespan=lifespan,
)

# Add rate limiter to app state
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# REST API routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["Sessions"])
app.include_router(video.router, prefix="/api/video", tags=["Video"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(export.router, prefix="/api/export", tags=["Export"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["Analysis"])
app.include_router(coaching.router, prefix="/api/coaching", tags=["Coaching"])
app.include_router(settings_routes.router, prefix="/api/settings", tags=["Settings"])

# WebSocket routes
app.include_router(ws_events.router, prefix="/ws", tags=["WebSocket"])
app.include_router(ws_video.router, prefix="/ws", tags=["WebSocket Video"])

# Static files for HLS streaming
app.mount("/hls", StaticFiles(directory=str(settings.data_directory / "hls")), name="hls")


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "app": settings.app_name, "version": "2.0.0"}


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "version": "2.0.0"}
