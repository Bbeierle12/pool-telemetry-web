from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2

logger = logging.getLogger(__name__)

Resolution = tuple[int, int]

# Standard resolution lookup table
RESOLUTION_PRESETS: dict[str, Resolution] = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "2.7k": (2704, 1520),
    "4k": (3840, 2160),
    # Additional common resolutions
    "480p": (854, 480),
    "1440p": (2560, 1440),
}


@dataclass
class VideoSettings:
    """Video capture settings."""

    resolution: Resolution | None = None
    framerate: float | None = None
    stabilization: bool = False
    buffer_size: int = 1


VideoSource = int | str


def parse_resolution(value: str) -> Resolution | None:
    """Parse a resolution string to width/height tuple.

    Args:
        value: Resolution string like '1080p', '4K', or '1920x1080'.

    Returns:
        Tuple of (width, height) or None if unparseable.
    """
    if not value:
        return None

    # Normalize to lowercase for lookup
    normalized = value.lower().strip()

    # Check preset lookup
    if normalized in RESOLUTION_PRESETS:
        return RESOLUTION_PRESETS[normalized]

    # Handle custom WxH format (case-insensitive)
    if "x" in normalized:
        parts = normalized.split("x")
        if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
            return int(parts[0]), int(parts[1])

    return None


def is_wifi_source(source: VideoSource) -> bool:
    """Check if the video source is a WiFi/network stream.

    Args:
        source: Video source (device index or URL).

    Returns:
        True if source is a network stream URL.
    """
    if isinstance(source, int):
        return False
    return source.startswith(("http://", "https://", "rtsp://", "udp://"))


def open_capture(source: VideoSource, settings: VideoSettings | None = None) -> cv2.VideoCapture:
    """Open a video capture device or stream.

    Args:
        source: Device index (int) or URL/path (str).
        settings: Optional video settings to apply.

    Returns:
        Opened cv2.VideoCapture instance.
    """
    # Determine backend based on source type
    if isinstance(source, str):
        if is_wifi_source(source):
            # Use FFmpeg backend for network streams
            cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
            logger.info("Opening network stream: %s", source)
        else:
            # File path
            cap = cv2.VideoCapture(source)
            logger.info("Opening video file: %s", source)
    else:
        # Device index - use platform default
        cap = cv2.VideoCapture(source)
        logger.info("Opening camera device: %d", source)

    if not cap.isOpened():
        logger.error("Failed to open video source: %s", source)
        return cap

    # Apply settings for live sources (not files)
    if settings and (isinstance(source, int) or is_wifi_source(source)):
        if settings.resolution:
            width, height = settings.resolution
            cap.set(cv2.CAP_PROP_FRAME_WIDTH, float(width))
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, float(height))
            logger.debug("Set resolution: %dx%d", width, height)

        if settings.framerate:
            cap.set(cv2.CAP_PROP_FPS, float(settings.framerate))
            logger.debug("Set framerate: %.1f", settings.framerate)

        if settings.buffer_size:
            cap.set(cv2.CAP_PROP_BUFFERSIZE, float(settings.buffer_size))
            logger.debug("Set buffer size: %d", settings.buffer_size)

    # Log actual capture properties
    actual_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    actual_fps = cap.get(cv2.CAP_PROP_FPS)
    logger.info(
        "Capture opened: %dx%d @ %.1f fps",
        actual_width,
        actual_height,
        actual_fps,
    )

    return cap


def get_capture_info(cap: cv2.VideoCapture) -> dict[str, float | int | str]:
    """Get information about an open video capture.

    Args:
        cap: Open cv2.VideoCapture instance.

    Returns:
        Dictionary with capture properties.
    """
    return {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
        "backend": cap.getBackendName(),
        "fourcc": int(cap.get(cv2.CAP_PROP_FOURCC)),
    }
