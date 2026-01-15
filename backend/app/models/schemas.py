"""Pydantic schemas for API request/response validation."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============= Profile Schemas =============

class ProfileCreate(BaseModel):
    """Create a new family profile."""
    name: str = Field(..., min_length=1, max_length=100)
    pin: str = Field(..., min_length=4, max_length=6)
    avatar: str = "default"


class ProfileResponse(BaseModel):
    """Profile response (no PIN)."""
    id: str
    name: str
    avatar: str
    created_at: datetime
    is_admin: bool

    class Config:
        from_attributes = True


class LoginRequest(BaseModel):
    """Login with PIN."""
    profile_id: str
    pin: str


class TokenResponse(BaseModel):
    """JWT token response."""
    access_token: str
    token_type: str = "bearer"
    profile: ProfileResponse


# ============= Session Schemas =============

class SessionCreate(BaseModel):
    """Create a new session."""
    name: Optional[str] = None
    source_type: str = Field(..., description="gopro_wifi, gopro_usb, or video_file")
    source_path: Optional[str] = None


class SessionUpdate(BaseModel):
    """Update session fields."""
    name: Optional[str] = None
    status: Optional[str] = None
    notes: Optional[str] = None
    total_shots: Optional[int] = None
    total_pocketed: Optional[int] = None
    total_fouls: Optional[int] = None
    gemini_cost_usd: Optional[float] = None


class SessionSummary(BaseModel):
    """Session list item."""
    id: str
    name: Optional[str]
    created_at: datetime
    status: str
    source_type: Optional[str]
    total_shots: int
    total_pocketed: int
    total_fouls: int
    duration_seconds: Optional[int] = None

    class Config:
        from_attributes = True


class SessionResponse(BaseModel):
    """Full session details."""
    id: str
    name: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    ended_at: Optional[datetime]
    status: str
    source_type: Optional[str]
    source_path: Optional[str]
    video_duration_ms: int
    video_resolution: Optional[str]
    video_framerate: Optional[int]
    total_shots: int
    total_pocketed: int
    total_fouls: int
    total_games: int
    gemini_cost_usd: float
    notes: Optional[str]
    extra_data: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


# ============= Event Schemas =============

class EventResponse(BaseModel):
    """Event data."""
    id: int
    session_id: str
    timestamp_ms: int
    event_type: str
    event_data: Optional[Dict[str, Any]]
    received_at: datetime

    class Config:
        from_attributes = True


class EventCreate(BaseModel):
    """Create event (from WebSocket)."""
    timestamp_ms: int
    event_type: str
    event_data: Optional[Dict[str, Any]] = None


# ============= Shot Schemas =============

class ShotResponse(BaseModel):
    """Shot data."""
    id: int
    session_id: str
    shot_number: int
    game_number: int
    timestamp_start_ms: Optional[int]
    timestamp_end_ms: Optional[int]
    duration_ms: Optional[int]
    balls_pocketed: Optional[List[str]]
    confidence_overall: Optional[float]

    class Config:
        from_attributes = True


class ShotDetail(ShotResponse):
    """Full shot details."""
    table_state_before: Optional[Dict[str, Any]]
    table_state_after: Optional[Dict[str, Any]]
    cue_ball_trajectory: Optional[Dict[str, Any]]
    collisions: Optional[List[Dict[str, Any]]]
    analysis_data: Optional[Dict[str, Any]]


# ============= Video Schemas =============

class GoProConfig(BaseModel):
    """GoPro connection settings."""
    connection_mode: str = Field(..., description="usb or wifi")
    wifi_ip: Optional[str] = None
    wifi_port: int = 8080
    protocol: str = "udp"  # udp, http, rtsp
    resolution: str = "1080p"
    framerate: int = 30
    stabilization: bool = True


class VideoUploadResponse(BaseModel):
    """Response after video upload."""
    session_id: str
    filename: str
    file_size_bytes: int
    duration_ms: Optional[int]
    stream_url: str


class StreamInfo(BaseModel):
    """HLS stream information."""
    session_id: str
    stream_url: str
    status: str  # ready, processing, error
    duration_ms: Optional[int]


# ============= Export Schemas =============

class ExportRequest(BaseModel):
    """Export request."""
    format: str = Field(..., description="full_json, claude_json, shots_csv, events_jsonl")
    include_frames: bool = False


class ExportResponse(BaseModel):
    """Export response."""
    download_url: str
    filename: str
    format: str
    file_size_bytes: int


# ============= Analysis Schemas =============

class BallPosition(BaseModel):
    """Ball position data for real-time updates."""
    ball_name: str
    x: float
    y: float
    confidence: float
    motion_state: str  # stationary, moving, decelerating


class BallUpdate(BaseModel):
    """Ball positions update (WebSocket message)."""
    type: str = "ball_update"
    timestamp_ms: int
    balls: List[BallPosition]


class GameEvent(BaseModel):
    """Game event (WebSocket message)."""
    type: str
    timestamp_ms: int
    data: Dict[str, Any]


# ============= Settings Schemas =============

class ApiKeysSettings(BaseModel):
    """API keys settings."""
    gemini_configured: bool
    anthropic_configured: bool


class GoProSettings(BaseModel):
    """GoPro default settings."""
    connection_mode: str = "wifi"
    wifi_ip: str = "10.5.5.9"
    resolution: str = "1080p"
    framerate: int = 30
    stabilization: bool = True


class StorageSettings(BaseModel):
    """Storage settings."""
    data_directory: str
    save_key_frames: bool = True
    save_raw_events: bool = True
    frame_quality: int = 85
    max_storage_gb: int = 50
    auto_cleanup_days: int = 90


class CostSettings(BaseModel):
    """Cost tracking settings."""
    enabled: bool = True
    warning_threshold: float = 5.0
    stop_threshold: float = 10.0


class SettingsResponse(BaseModel):
    """All settings."""
    api_keys: ApiKeysSettings
    gopro: GoProSettings
    storage: StorageSettings
    cost: CostSettings


class SettingsUpdate(BaseModel):
    """Update settings."""
    gopro: Optional[GoProSettings] = None
    storage: Optional[StorageSettings] = None
    cost: Optional[CostSettings] = None
