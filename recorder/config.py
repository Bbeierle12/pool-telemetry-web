from __future__ import annotations

import json
import logging
import os
import stat
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def default_data_dir() -> Path:
    """Return the default data directory path (~/.pool_telemetry)."""
    return Path.home() / ".pool_telemetry"


def default_config_path() -> Path:
    """Return the default config file path (~/.pool_telemetry/config.json)."""
    return default_data_dir() / "config.json"


@dataclass
class ApiKeys:
    gemini: str | None = None
    anthropic: str | None = None


@dataclass
class GoProConfig:
    connection_mode: str = "usb_webcam"
    wifi_ip: str | None = None
    resolution: str = "1080p"
    framerate: int = 60
    stabilization: bool = True


@dataclass
class VideoImportConfig:
    default_directory: str = "~/Videos"
    supported_formats: list[str] = field(default_factory=lambda: ["mp4", "mov", "mkv", "avi"])
    max_file_size_gb: int = 10


@dataclass
class GeminiConfig:
    model: str = "gemini-2.0-flash-live"
    frame_sample_rate_ms: int = 33
    reconnect_attempts: int = 3
    reconnect_delay_ms: int = 1000
    system_prompt: str = (
        "You are a pool telemetry extractor. Return structured JSON events for shots, "
        "collisions, cushions, pockets, fouls, and table state updates."
    )


@dataclass
class StorageConfig:
    data_directory: str = str(default_data_dir())
    save_key_frames: bool = True
    save_raw_events: bool = True
    frame_quality: int = 85
    max_storage_gb: int = 50
    auto_cleanup_days: int = 90


@dataclass
class UiConfig:
    theme: str = "dark"
    video_preview_size: str = "medium"
    show_raw_json: bool = False
    show_trajectory_overlay: bool = True
    event_log_max_lines: int = 500


@dataclass
class CostTrackingConfig:
    enabled: bool = True
    warn_threshold_usd: float = 5.0
    stop_threshold_usd: float | None = None


@dataclass
class AppConfig:
    version: str = "1.0.0"
    api_keys: ApiKeys = field(default_factory=ApiKeys)
    gopro: GoProConfig = field(default_factory=GoProConfig)
    video_import: VideoImportConfig = field(default_factory=VideoImportConfig)
    gemini: GeminiConfig = field(default_factory=GeminiConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
    ui: UiConfig = field(default_factory=UiConfig)
    cost_tracking: CostTrackingConfig = field(default_factory=CostTrackingConfig)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in updates.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _config_from_dict(data: dict[str, Any]) -> AppConfig:
    defaults = AppConfig().to_dict()
    merged = _deep_merge(defaults, data)
    return AppConfig(
        version=merged["version"],
        api_keys=ApiKeys(**merged["api_keys"]),
        gopro=GoProConfig(**merged["gopro"]),
        video_import=VideoImportConfig(**merged["video_import"]),
        gemini=GeminiConfig(**merged["gemini"]),
        storage=StorageConfig(**merged["storage"]),
        ui=UiConfig(**merged["ui"]),
        cost_tracking=CostTrackingConfig(**merged["cost_tracking"]),
    )


def _check_config_security(config_path: Path, config: AppConfig) -> None:
    """Check and warn about config file security issues."""
    has_api_keys = config.api_keys.gemini or config.api_keys.anthropic

    if not has_api_keys:
        return

    # Warn about plain-text API key storage
    logger.warning(
        "API keys are stored in plain text at %s. "
        "Consider using environment variables (GEMINI_API_KEY, ANTHROPIC_API_KEY) "
        "for production use.",
        config_path,
    )

    # On Unix systems, check file permissions
    if os.name != "nt":
        try:
            mode = config_path.stat().st_mode
            if mode & (stat.S_IRWXG | stat.S_IRWXO):
                logger.warning(
                    "Config file %s has group/world permissions. "
                    "Consider restricting with: chmod 600 %s",
                    config_path,
                    config_path,
                )
        except OSError:
            pass


def load_config(path: Path | None = None) -> AppConfig:
    """Load application configuration from JSON file.

    Args:
        path: Optional path to config file. Defaults to ~/.pool_telemetry/config.json.

    Returns:
        AppConfig instance with loaded or default values.
    """
    config_path = path or default_config_path()
    if not config_path.exists():
        return AppConfig()
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    config = _config_from_dict(raw)
    _check_config_security(config_path, config)
    return config


def save_config(config: AppConfig, path: Path | None = None) -> Path:
    """Save application configuration to JSON file.

    Args:
        config: AppConfig instance to save.
        path: Optional path for config file. Defaults to ~/.pool_telemetry/config.json.

    Returns:
        Path to the saved config file.
    """
    config_path = path or default_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config.to_dict(), indent=2), encoding="utf-8")
    return config_path
