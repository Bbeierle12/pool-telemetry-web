"""Settings API routes for application configuration."""
from __future__ import annotations

import json
import logging
import shutil
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.core.auth import get_current_profile, require_admin
from app.models.database import Profile

router = APIRouter()
logger = logging.getLogger(__name__)

# Settings file path
SETTINGS_FILE = settings.data_directory / "user_settings.json"


class ApiKeysSettings(BaseModel):
    gemini_key: Optional[str] = None
    anthropic_key: Optional[str] = None


class ApiKeysResponse(BaseModel):
    """Response model that masks API keys for security."""
    gemini_key_configured: bool = False
    anthropic_key_configured: bool = False
    gemini_key_preview: Optional[str] = None
    anthropic_key_preview: Optional[str] = None


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


class AllSettingsResponse(BaseModel):
    """Response model with masked API keys."""
    api_keys: ApiKeysResponse = Field(default_factory=ApiKeysResponse)
    gopro: GoProSettings = Field(default_factory=GoProSettings)
    video: VideoSettings = Field(default_factory=VideoSettings)
    analysis: AnalysisSettings = Field(default_factory=AnalysisSettings)
    storage: StorageSettings = Field(default_factory=StorageSettings)
    cost: CostSettings = Field(default_factory=CostSettings)
    display: DisplaySettings = Field(default_factory=DisplaySettings)
    notifications: NotificationSettings = Field(default_factory=NotificationSettings)


def _mask_key(key: Optional[str]) -> Optional[str]:
    """Return last 4 characters of key, or None if too short."""
    if not key or len(key) < 8:
        return None
    return f"...{key[-4:]}"


def _mask_api_keys(api_keys: ApiKeysSettings) -> ApiKeysResponse:
    """Create a masked response from API keys settings."""
    return ApiKeysResponse(
        gemini_key_configured=bool(api_keys.gemini_key),
        anthropic_key_configured=bool(api_keys.anthropic_key),
        gemini_key_preview=_mask_key(api_keys.gemini_key),
        anthropic_key_preview=_mask_key(api_keys.anthropic_key),
    )


async def load_settings() -> AllSettings:
    """Load settings from file or return defaults."""
    if SETTINGS_FILE.exists():
        try:
            async with aiofiles.open(SETTINGS_FILE, "r") as f:
                content = await f.read()
            data = json.loads(content)
            return AllSettings(**data)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse settings file: {e}")
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
    return AllSettings()


async def save_settings(user_settings: AllSettings) -> None:
    """Save settings to file."""
    try:
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        async with aiofiles.open(SETTINGS_FILE, "w") as f:
            await f.write(user_settings.model_dump_json(indent=2))
    except Exception as e:
        logger.error(f"Failed to save settings: {e}")
        raise HTTPException(status_code=500, detail="Failed to save settings")


@router.get("", response_model=AllSettingsResponse)
async def get_all_settings(
    profile: Profile = Depends(get_current_profile),
):
    """Get all application settings (API keys are masked)."""
    user_settings = await load_settings()
    return AllSettingsResponse(
        api_keys=_mask_api_keys(user_settings.api_keys),
        gopro=user_settings.gopro,
        video=user_settings.video,
        analysis=user_settings.analysis,
        storage=user_settings.storage,
        cost=user_settings.cost,
        display=user_settings.display,
        notifications=user_settings.notifications,
    )


@router.put("", response_model=AllSettingsResponse)
async def update_all_settings(
    new_settings: AllSettings,
    profile: Profile = Depends(require_admin),
):
    """Update all application settings (admin only)."""
    await save_settings(new_settings)
    return AllSettingsResponse(
        api_keys=_mask_api_keys(new_settings.api_keys),
        gopro=new_settings.gopro,
        video=new_settings.video,
        analysis=new_settings.analysis,
        storage=new_settings.storage,
        cost=new_settings.cost,
        display=new_settings.display,
        notifications=new_settings.notifications,
    )


@router.get("/api-keys", response_model=ApiKeysResponse)
async def get_api_key_status(
    profile: Profile = Depends(require_admin),
):
    """Get API key configuration status (admin only)."""
    user_settings = await load_settings()
    return _mask_api_keys(user_settings.api_keys)


@router.patch("/api-keys", response_model=ApiKeysResponse)
async def update_api_keys(
    api_keys: ApiKeysSettings,
    profile: Profile = Depends(require_admin),
):
    """Update API keys (admin only)."""
    current = await load_settings()
    current.api_keys = api_keys
    await save_settings(current)
    return _mask_api_keys(api_keys)


@router.patch("/gopro", response_model=GoProSettings)
async def update_gopro_settings(
    gopro: GoProSettings,
    profile: Profile = Depends(get_current_profile),
):
    """Update GoPro settings."""
    current = await load_settings()
    current.gopro = gopro
    await save_settings(current)
    return gopro


@router.patch("/analysis", response_model=AnalysisSettings)
async def update_analysis_settings(
    analysis: AnalysisSettings,
    profile: Profile = Depends(get_current_profile),
):
    """Update analysis/AI settings."""
    current = await load_settings()
    current.analysis = analysis
    await save_settings(current)
    return analysis


@router.patch("/storage", response_model=StorageSettings)
async def update_storage_settings(
    storage: StorageSettings,
    profile: Profile = Depends(require_admin),
):
    """Update storage settings (admin only)."""
    current = await load_settings()
    current.storage = storage
    await save_settings(current)
    return storage


@router.patch("/display", response_model=DisplaySettings)
async def update_display_settings(
    display: DisplaySettings,
    profile: Profile = Depends(get_current_profile),
):
    """Update display settings."""
    current = await load_settings()
    current.display = display
    await save_settings(current)
    return display


class StorageInfo(BaseModel):
    total_size_mb: float
    sessions_count: int
    videos_count: int
    exports_count: int
    hls_size_mb: float
    uploads_size_mb: float


@router.get("/storage/info", response_model=StorageInfo)
async def get_storage_info(
    profile: Profile = Depends(get_current_profile),
):
    """Get storage usage information."""
    def get_dir_size(path: Path) -> float:
        if not path.exists():
            return 0
        try:
            total = sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
            return total / (1024 * 1024)  # MB
        except Exception as e:
            logger.warning(f"Error calculating directory size for {path}: {e}")
            return 0

    def count_files(path: Path, pattern: str = "*") -> int:
        if not path.exists():
            return 0
        try:
            return len(list(path.rglob(pattern)))
        except Exception as e:
            logger.warning(f"Error counting files in {path}: {e}")
            return 0

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
    errors: int = 0


@router.post("/storage/cleanup", response_model=CleanupResult)
async def cleanup_storage(
    older_than_days: int = 30,
    profile: Profile = Depends(require_admin),
):
    """Clean up old data from storage (admin only)."""
    import time

    cutoff = time.time() - (older_than_days * 24 * 60 * 60)
    deleted = 0
    freed = 0
    errors = 0

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
                except Exception as e:
                    logger.warning(f"Failed to cleanup {session_dir}: {e}")
                    errors += 1

    return CleanupResult(
        deleted_count=deleted,
        freed_mb=freed / (1024 * 1024),
        errors=errors,
    )


@router.post("/storage/clear-cache")
async def clear_cache(
    profile: Profile = Depends(require_admin),
):
    """Clear all cached data - HLS segments, temp files (admin only)."""
    cleared = 0
    errors = 0

    # Clear HLS cache
    hls_dir = settings.data_directory / "hls"
    if hls_dir.exists():
        for item in hls_dir.iterdir():
            if item.is_dir():
                try:
                    shutil.rmtree(item)
                    cleared += 1
                except Exception as e:
                    logger.warning(f"Failed to clear cache item {item}: {e}")
                    errors += 1

    return {"message": f"Cleared {cleared} cached items", "errors": errors}


@router.get("/system/info")
async def get_system_info(
    profile: Profile = Depends(get_current_profile),
):
    """Get system information for diagnostics."""
    import platform
    import sys

    try:
        import cv2
        opencv_version = cv2.__version__
    except ImportError:
        opencv_version = "Not installed"

    # Don't expose full paths - only relative info
    return {
        "app_version": "2.0.0",
        "python_version": sys.version.split()[0],  # Just version number
        "platform": platform.system(),
        "opencv_version": opencv_version,
        "gemini_configured": settings.gemini_api_key is not None,
        "anthropic_configured": settings.anthropic_api_key is not None,
    }


@router.post("/reset")
async def reset_settings(
    profile: Profile = Depends(require_admin),
):
    """Reset all settings to defaults (admin only)."""
    default_settings = AllSettings()
    await save_settings(default_settings)
    return {
        "message": "Settings reset to defaults",
        "settings": AllSettingsResponse(
            api_keys=_mask_api_keys(default_settings.api_keys),
            gopro=default_settings.gopro,
            video=default_settings.video,
            analysis=default_settings.analysis,
            storage=default_settings.storage,
            cost=default_settings.cost,
            display=default_settings.display,
            notifications=default_settings.notifications,
        )
    }
