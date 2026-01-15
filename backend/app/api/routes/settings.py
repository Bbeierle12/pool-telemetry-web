"""Settings API routes for application configuration."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.config import settings

router = APIRouter()

# Settings file path
SETTINGS_FILE = settings.data_directory / "user_settings.json"


class ApiKeysSettings(BaseModel):
    gemini_key: Optional[str] = None
    anthropic_key: Optional[str] = None


class GoProSettings(BaseModel):
    connection_mode: str = "wifi"
    wifi_ip: str = "10.5.5.9"
    wifi_port: int = 8080
    protocol: str = "udp"
    resolution: str = "1080p"
    framerate: int = 30
    stabilization: bool = True


class VideoSettings(BaseModel):
    default_resolution: str = "1080p"
    default_framerate: int = 30
    hls_segment_duration: int = 2
    save_original: bool = True
    auto_process: bool = True


class AnalysisSettings(BaseModel):
    ai_provider: str = "gemini"  # gemini, anthropic, none
    gemini_model: str = "gemini-2.0-flash-exp"
    anthropic_model: str = "claude-3-5-sonnet-20241022"
    frame_sample_rate_ms: int = 33
    enable_ball_tracking: bool = True
    enable_shot_detection: bool = True
    enable_foul_detection: bool = True
    confidence_threshold: float = 0.7
    system_prompt: str = (
        "You are a pool/billiards telemetry extractor. Analyze video frames and return "
        "structured JSON events for shots, collisions, cushions, pockets, fouls, and ball positions."
    )


class StorageSettings(BaseModel):
    data_directory: str = "./data"
    save_key_frames: bool = True
    save_raw_events: bool = True
    frame_quality: int = 85
    max_storage_gb: int = 50
    auto_cleanup_days: int = 90


class CostSettings(BaseModel):
    enabled: bool = True
    warning_threshold: float = 5.0
    stop_threshold: float = 10.0
    track_per_session: bool = True


class DisplaySettings(BaseModel):
    theme: str = "dark"
    show_ball_labels: bool = True
    show_trajectory: bool = True
    show_confidence: bool = True
    event_log_max_lines: int = 500
    auto_scroll_events: bool = True
    compact_mode: bool = False


class NotificationSettings(BaseModel):
    enable_sounds: bool = False
    enable_desktop: bool = True
    notify_on_shot: bool = False
    notify_on_foul: bool = True
    notify_on_pocket: bool = False
    notify_on_cost_warning: bool = True


class AllSettings(BaseModel):
    api_keys: ApiKeysSettings = Field(default_factory=ApiKeysSettings)
    gopro: GoProSettings = Field(default_factory=GoProSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    cost: CostSettings = Field(default_factory=CostSettings)
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


def load_settings() -> AllSettings:
    """Load settings from file or return defaults."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text())
            return AllSettings(**data)
        except Exception:
            pass
    return AllSettings()


def save_settings(user_settings: AllSettings) -> None:
    """Save settings to file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SETTINGS_FILE.write_text(user_settings.model_dump_json(indent=2))


@router.get("", response_model=AllSettings)
async def get_all_settings():
    """Get all application settings."""
    return load_settings()


@router.put("", response_model=AllSettings)
async def update_all_settings(new_settings: AllSettings):
    """Update all application settings."""
    save_settings(new_settings)
    return new_settings


@router.patch("/api-keys", response_model=ApiKeysSettings)
async def update_api_keys(api_keys: ApiKeysSettings):
    """Update API keys only."""
    current = load_settings()
    current.api_keys = api_keys
    save_settings(current)
    return api_keys


@router.patch("/gopro", response_model=GoProSettings)
async def update_gopro_settings(gopro: GoProSettings):
    """Update GoPro settings only."""
    current = load_settings()
    current.gopro = gopro
    save_settings(current)
    return gopro


@router.patch("/analysis", response_model=AnalysisSettings)
async def update_analysis_settings(analysis: AnalysisSettings):
    """Update analysis/AI settings only."""
    current = load_settings()
    current.analysis = analysis
    save_settings(current)
    return analysis


@router.patch("/storage", response_model=StorageSettings)
async def update_storage_settings(storage: StorageSettings):
    """Update storage settings only."""
    current = load_settings()
    current.storage = storage
    save_settings(current)
    return storage


@router.patch("/display", response_model=DisplaySettings)
async def update_display_settings(display: DisplaySettings):
    """Update display settings only."""
    current = load_settings()
    current.display = display
    save_settings(current)
    return display


class StorageInfo(BaseModel):
    total_size_mb: float
    sessions_count: int
    videos_count: int
    exports_count: int
    hls_size_mb: float
    uploads_size_mb: float


@router.get("/storage/info", response_model=StorageInfo)
async def get_storage_info():
    """Get storage usage information."""
    def get_dir_size(path: Path) -> float:
        if not path.exists():
            return 0
        total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
        return total / (1024 * 1024)  # MB

    def count_files(path: Path, pattern: str = "*") -> int:
        if not path.exists():
            return 0
        return len(list(path.rglob(pattern)))

    data_dir = settings.data_directory

    return StorageInfo(
        total_size_mb=get_dir_size(data_dir),
        sessions_count=count_files(data_dir / "sessions", "*"),
        videos_count=count_files(data_dir / "uploads", "*.mp4") + count_files(data_dir / "uploads", "*.mov"),
        exports_count=count_files(data_dir / "exports", "*"),
        hls_size_mb=get_dir_size(data_dir / "hls"),
        uploads_size_mb=get_dir_size(data_dir / "uploads"),
    )


class CleanupResult(BaseModel):
    deleted_count: int
    freed_mb: float


@router.post("/storage/cleanup", response_model=CleanupResult)
async def cleanup_storage(older_than_days: int = 30):
    """Clean up old data from storage."""
    import time
    from datetime import datetime, timedelta

    cutoff = time.time() - (older_than_days * 24 * 60 * 60)
    deleted = 0
    freed = 0

    # Clean up HLS segments older than cutoff
    hls_dir = settings.data_directory / "hls"
    if hls_dir.exists():
        for session_dir in hls_dir.iterdir():
            if session_dir.is_dir():
                try:
                    mtime = session_dir.stat().st_mtime
                    if mtime < cutoff:
                        size = sum(f.stat().st_size for f in session_dir.rglob("*") if f.is_file())
                        shutil.rmtree(session_dir)
                        deleted += 1
                        freed += size
                except Exception:
                    pass

    return CleanupResult(
        deleted_count=deleted,
        freed_mb=freed / (1024 * 1024),
    )


@router.post("/storage/clear-cache")
async def clear_cache():
    """Clear all cached data (HLS segments, temp files)."""
    cleared = 0

    # Clear HLS cache
    hls_dir = settings.data_directory / "hls"
    if hls_dir.exists():
        for item in hls_dir.iterdir():
            if item.is_dir():
                shutil.rmtree(item)
                cleared += 1

    return {"message": f"Cleared {cleared} cached items"}


@router.get("/system/info")
async def get_system_info():
    """Get system information for diagnostics."""
    import platform
    import sys

    try:
        import cv2
        opencv_version = cv2.__version__
    except ImportError:
        opencv_version = "Not installed"

    return {
        "app_version": "2.0.0",
        "python_version": sys.version,
        "platform": platform.platform(),
        "opencv_version": opencv_version,
        "data_directory": str(settings.data_directory),
        "database_url": settings.database_url.split("///")[-1],  # Hide full path
        "gemini_configured": settings.gemini_api_key is not None,
        "anthropic_configured": settings.anthropic_api_key is not None,
    }


@router.post("/reset")
async def reset_settings():
    """Reset all settings to defaults."""
    default_settings = AllSettings()
    save_settings(default_settings)
    return {"message": "Settings reset to defaults", "settings": default_settings}
