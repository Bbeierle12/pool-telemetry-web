"""Storage management for session data, frames, and cleanup."""

from __future__ import annotations

import json
import logging
import shutil
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import cv2
import numpy as np

if TYPE_CHECKING:
    from .config import StorageConfig

logger = logging.getLogger(__name__)


@dataclass
class StorageStats:
    """Statistics about storage usage."""

    total_bytes: int
    session_count: int
    frame_count: int
    oldest_session_date: str | None
    newest_session_date: str | None

    @property
    def total_gb(self) -> float:
        """Total storage in gigabytes."""
        return self.total_bytes / (1024 ** 3)

    def to_dict(self) -> dict:
        """Convert to dictionary."""
        return {**asdict(self), "total_gb": self.total_gb}


@dataclass
class SessionStorage:
    """Paths for a session's storage."""

    session_id: str
    root: Path
    frames_dir: Path
    thumbnails_dir: Path
    metadata_path: Path

    def ensure_dirs(self) -> None:
        """Create all directories if they don't exist."""
        self.root.mkdir(parents=True, exist_ok=True)
        self.frames_dir.mkdir(exist_ok=True)
        self.thumbnails_dir.mkdir(exist_ok=True)


class StorageManager:
    """Manages file storage for sessions, frames, and exports."""

    def __init__(self, config: StorageConfig) -> None:
        """Initialize storage manager.

        Args:
            config: Storage configuration.
        """
        self._config = config
        self._data_dir = Path(config.data_directory)
        self._sessions_dir = self._data_dir / "sessions"
        self._exports_dir = self._data_dir / "exports"
        self._ensure_base_dirs()

    def _ensure_base_dirs(self) -> None:
        """Create base directory structure."""
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._sessions_dir.mkdir(exist_ok=True)
        self._exports_dir.mkdir(exist_ok=True)

    @property
    def data_directory(self) -> Path:
        """Get the root data directory."""
        return self._data_dir

    @property
    def sessions_directory(self) -> Path:
        """Get the sessions directory."""
        return self._sessions_dir

    @property
    def exports_directory(self) -> Path:
        """Get the exports directory."""
        return self._exports_dir

    def get_session_storage(self, session_id: str) -> SessionStorage:
        """Get storage paths for a session.

        Args:
            session_id: Unique session identifier.

        Returns:
            SessionStorage with all paths configured.
        """
        root = self._sessions_dir / session_id
        return SessionStorage(
            session_id=session_id,
            root=root,
            frames_dir=root / "frames",
            thumbnails_dir=root / "thumbnails",
            metadata_path=root / "metadata.json",
        )

    def create_session_storage(self, session_id: str, metadata: dict | None = None) -> SessionStorage:
        """Create storage directories for a new session.

        Args:
            session_id: Unique session identifier.
            metadata: Optional metadata to save.

        Returns:
            SessionStorage with directories created.
        """
        storage = self.get_session_storage(session_id)
        storage.ensure_dirs()

        # Write initial metadata
        meta = {
            "session_id": session_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "frames_saved": 0,
            "thumbnails_saved": 0,
            **(metadata or {}),
        }
        self._write_json(storage.metadata_path, meta)
        logger.info("Created session storage: %s", storage.root)
        return storage

    def save_frame(
        self,
        session_id: str,
        frame: np.ndarray,
        frame_type: str,
        shot_number: int | None = None,
        timestamp_ms: int | None = None,
    ) -> Path | None:
        """Save a video frame to disk.

        Args:
            session_id: Session identifier.
            frame: OpenCV frame (BGR format).
            frame_type: Type of frame (e.g., "pre_shot", "post_shot", "key_frame").
            shot_number: Optional shot number for naming.
            timestamp_ms: Optional timestamp in milliseconds.

        Returns:
            Path to saved frame, or None if saving disabled/failed.
        """
        if not self._config.save_key_frames:
            return None

        storage = self.get_session_storage(session_id)
        storage.frames_dir.mkdir(parents=True, exist_ok=True)

        # Build filename
        parts = []
        if shot_number is not None:
            parts.append(f"shot_{shot_number:04d}")
        parts.append(frame_type)
        if timestamp_ms is not None:
            parts.append(f"t{timestamp_ms}")
        filename = "_".join(parts) + ".jpg"
        frame_path = storage.frames_dir / filename

        # Save with configured quality
        success = self._save_image(frame_path, frame, self._config.frame_quality)
        if success:
            self._increment_metadata_counter(storage, "frames_saved")
            logger.debug("Saved frame: %s", frame_path)
            return frame_path
        return None

    def save_thumbnail(
        self,
        session_id: str,
        frame: np.ndarray,
        name: str,
        size: tuple[int, int] = (320, 180),
    ) -> Path | None:
        """Save a thumbnail image.

        Args:
            session_id: Session identifier.
            frame: OpenCV frame (BGR format).
            name: Thumbnail name (without extension).
            size: Thumbnail dimensions (width, height).

        Returns:
            Path to saved thumbnail, or None if failed.
        """
        storage = self.get_session_storage(session_id)
        storage.thumbnails_dir.mkdir(parents=True, exist_ok=True)

        # Resize frame
        thumbnail = cv2.resize(frame, size, interpolation=cv2.INTER_AREA)
        thumb_path = storage.thumbnails_dir / f"{name}.jpg"

        success = self._save_image(thumb_path, thumbnail, 80)
        if success:
            self._increment_metadata_counter(storage, "thumbnails_saved")
            logger.debug("Saved thumbnail: %s", thumb_path)
            return thumb_path
        return None

    def get_session_thumbnail(self, session_id: str) -> Path | None:
        """Get the main thumbnail for a session.

        Args:
            session_id: Session identifier.

        Returns:
            Path to thumbnail if exists, None otherwise.
        """
        storage = self.get_session_storage(session_id)
        thumb_path = storage.thumbnails_dir / "session_thumb.jpg"
        if thumb_path.exists():
            return thumb_path
        # Fallback to first thumbnail
        if storage.thumbnails_dir.exists():
            thumbs = list(storage.thumbnails_dir.glob("*.jpg"))
            if thumbs:
                return thumbs[0]
        return None

    def link_source_video(self, session_id: str, video_path: str) -> None:
        """Record the source video path for a session.

        Args:
            session_id: Session identifier.
            video_path: Path to the source video.
        """
        storage = self.get_session_storage(session_id)
        storage.root.mkdir(parents=True, exist_ok=True)
        link_file = storage.root / "source_video.txt"
        link_file.write_text(video_path, encoding="utf-8")
        logger.debug("Linked source video: %s", video_path)

    def update_session_metadata(self, session_id: str, updates: dict) -> None:
        """Update session metadata.

        Args:
            session_id: Session identifier.
            updates: Dictionary of updates to merge.
        """
        storage = self.get_session_storage(session_id)
        if not storage.metadata_path.exists():
            return
        meta = self._read_json(storage.metadata_path)
        meta.update(updates)
        meta["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._write_json(storage.metadata_path, meta)

    def get_session_metadata(self, session_id: str) -> dict | None:
        """Get session metadata.

        Args:
            session_id: Session identifier.

        Returns:
            Metadata dictionary or None if not found.
        """
        storage = self.get_session_storage(session_id)
        if storage.metadata_path.exists():
            return self._read_json(storage.metadata_path)
        return None

    def list_session_frames(self, session_id: str) -> list[Path]:
        """List all frames for a session.

        Args:
            session_id: Session identifier.

        Returns:
            List of frame paths sorted by name.
        """
        storage = self.get_session_storage(session_id)
        if not storage.frames_dir.exists():
            return []
        return sorted(storage.frames_dir.glob("*.jpg"))

    def delete_session_storage(self, session_id: str) -> bool:
        """Delete all storage for a session.

        Args:
            session_id: Session identifier.

        Returns:
            True if deleted, False if not found.
        """
        storage = self.get_session_storage(session_id)
        if storage.root.exists():
            shutil.rmtree(storage.root)
            logger.info("Deleted session storage: %s", storage.root)
            return True
        return False

    def get_storage_stats(self) -> StorageStats:
        """Calculate storage statistics.

        Returns:
            StorageStats with usage information.
        """
        total_bytes = 0
        session_count = 0
        frame_count = 0
        oldest_date: str | None = None
        newest_date: str | None = None

        if not self._sessions_dir.exists():
            return StorageStats(0, 0, 0, None, None)

        for session_dir in self._sessions_dir.iterdir():
            if not session_dir.is_dir():
                continue
            session_count += 1

            # Count frames
            frames_dir = session_dir / "frames"
            if frames_dir.exists():
                frames = list(frames_dir.glob("*.jpg"))
                frame_count += len(frames)

            # Calculate size
            for file in session_dir.rglob("*"):
                if file.is_file():
                    total_bytes += file.stat().st_size

            # Track dates from metadata
            meta_path = session_dir / "metadata.json"
            if meta_path.exists():
                meta = self._read_json(meta_path)
                created = meta.get("created_at")
                if created:
                    if oldest_date is None or created < oldest_date:
                        oldest_date = created
                    if newest_date is None or created > newest_date:
                        newest_date = created

        return StorageStats(
            total_bytes=total_bytes,
            session_count=session_count,
            frame_count=frame_count,
            oldest_session_date=oldest_date,
            newest_session_date=newest_date,
        )

    def check_storage_quota(self) -> tuple[bool, float]:
        """Check if storage is within quota.

        Returns:
            Tuple of (is_within_quota, current_usage_gb).
        """
        stats = self.get_storage_stats()
        max_gb = self._config.max_storage_gb
        return stats.total_gb < max_gb, stats.total_gb

    def cleanup_old_sessions(self, db_session_ids: set[str] | None = None) -> int:
        """Remove sessions older than auto_cleanup_days.

        Args:
            db_session_ids: Optional set of session IDs still in database.
                           If provided, only cleans up orphaned storage.

        Returns:
            Number of sessions cleaned up.
        """
        if self._config.auto_cleanup_days <= 0:
            return 0

        cutoff = datetime.now(timezone.utc).timestamp() - (
            self._config.auto_cleanup_days * 24 * 60 * 60
        )
        cleaned = 0

        if not self._sessions_dir.exists():
            return 0

        for session_dir in list(self._sessions_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            session_id = session_dir.name

            # If we have DB session IDs, only clean orphaned storage
            if db_session_ids is not None and session_id in db_session_ids:
                continue

            # Check metadata for created_at
            meta_path = session_dir / "metadata.json"
            should_delete = False

            if meta_path.exists():
                meta = self._read_json(meta_path)
                created_at = meta.get("created_at")
                if created_at:
                    try:
                        created_ts = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
                        if created_ts < cutoff:
                            should_delete = True
                    except ValueError:
                        pass
            else:
                # No metadata, check directory mtime
                if session_dir.stat().st_mtime < cutoff:
                    should_delete = True

            if should_delete:
                shutil.rmtree(session_dir)
                logger.info("Cleaned up old session: %s", session_id)
                cleaned += 1

        return cleaned

    def cleanup_orphaned_storage(self, db_session_ids: set[str]) -> int:
        """Remove storage for sessions not in database.

        Args:
            db_session_ids: Set of session IDs that exist in database.

        Returns:
            Number of orphaned sessions cleaned up.
        """
        cleaned = 0

        if not self._sessions_dir.exists():
            return 0

        for session_dir in list(self._sessions_dir.iterdir()):
            if not session_dir.is_dir():
                continue

            session_id = session_dir.name
            if session_id not in db_session_ids:
                shutil.rmtree(session_dir)
                logger.info("Cleaned up orphaned session storage: %s", session_id)
                cleaned += 1

        return cleaned

    def _save_image(self, path: Path, image: np.ndarray, quality: int) -> bool:
        """Save image with error handling.

        Args:
            path: Output path.
            image: OpenCV image.
            quality: JPEG quality (1-100).

        Returns:
            True if successful.
        """
        try:
            params = [cv2.IMWRITE_JPEG_QUALITY, quality]
            success = cv2.imwrite(str(path), image, params)
            return success
        except Exception as e:
            logger.error("Failed to save image %s: %s", path, e)
            return False

    def _read_json(self, path: Path) -> dict:
        """Read JSON file."""
        return json.loads(path.read_text(encoding="utf-8"))

    def _write_json(self, path: Path, data: dict) -> None:
        """Write JSON file."""
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def _increment_metadata_counter(self, storage: SessionStorage, key: str) -> None:
        """Increment a counter in session metadata."""
        if not storage.metadata_path.exists():
            return
        meta = self._read_json(storage.metadata_path)
        meta[key] = meta.get(key, 0) + 1
        self._write_json(storage.metadata_path, meta)
