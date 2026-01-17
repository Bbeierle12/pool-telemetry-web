"""WebSocket handler for live video streaming."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import async_session
from app.core.auth import verify_ws_token
from app.models.database import Session

router = APIRouter()
logger = logging.getLogger(__name__)

# Thread pool for blocking OpenCV operations
_executor = ThreadPoolExecutor(max_workers=4)


class CameraManager:
    """Manage USB camera capture and streaming."""

    def __init__(self):
        self.active_cameras: Dict[str, cv2.VideoCapture] = {}
        self._lock = asyncio.Lock()

    def _open_camera(
        self,
        device_index: int,
        resolution: str,
        framerate: int
    ) -> Optional[cv2.VideoCapture]:
        """Open camera (runs in thread pool)."""
        print(f"[VIDEO] Attempting to open camera {device_index}")

        # Try different backends
        backends = [
            (cv2.CAP_DSHOW, "DirectShow"),
            (cv2.CAP_MSMF, "Media Foundation"),
            (cv2.CAP_ANY, "Default"),
        ]

        cap = None
        for backend, name in backends:
            print(f"[VIDEO] Trying {name} backend...")
            cap = cv2.VideoCapture(device_index, backend)
            if cap.isOpened():
                print(f"[VIDEO] Success with {name} backend")
                break
            cap.release()
            cap = None

        if not cap or not cap.isOpened():
            print(f"[VIDEO] Failed to open camera {device_index} with any backend")
            return None

        # Set resolution
        res_map = {
            "720p": (1280, 720),
            "1080p": (1920, 1080),
            "4K": (3840, 2160),
            "2.7K": (2704, 1520),
        }
        width, height = res_map.get(resolution, (1920, 1080))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        cap.set(cv2.CAP_PROP_FPS, framerate)

        # Read actual settings
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"[VIDEO] Camera opened: {actual_w}x{actual_h} @ {actual_fps}fps")

        # Test read a frame
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[VIDEO] Test frame captured: {frame.shape}")
            # Save test frame to disk for debugging
            test_path = f"test_frame_{device_index}.jpg"
            cv2.imwrite(test_path, frame)
            print(f"[VIDEO] Test frame saved to: {test_path}")
        else:
            print(f"[VIDEO] WARNING: Test frame capture failed!")

        return cap

    async def start_capture(
        self,
        session_id: str,
        device_index: int = 0,
        resolution: str = "1080p",
        framerate: int = 30
    ) -> bool:
        """Start capturing from a USB camera."""
        async with self._lock:
            if session_id in self.active_cameras:
                return True  # Already capturing

            loop = asyncio.get_event_loop()
            cap = await loop.run_in_executor(
                _executor,
                self._open_camera,
                device_index,
                resolution,
                framerate
            )

            if not cap:
                return False

            self.active_cameras[session_id] = cap
            return True

    async def stop_capture(self, session_id: str):
        """Stop capturing from a camera."""
        async with self._lock:
            if session_id in self.active_cameras:
                cap = self.active_cameras.pop(session_id)
                cap.release()
                logger.info(f"Camera released for session {session_id}")

    def _read_frame(self, cap: cv2.VideoCapture) -> Tuple[bool, Optional[bytes]]:
        """Read and encode a frame (runs in thread pool)."""
        ret, frame = cap.read()
        if not ret or frame is None:
            print("[VIDEO] Frame read failed")
            return False, None

        # Encode as JPEG
        success, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if not success:
            print("[VIDEO] JPEG encode failed")
            return False, None

        return True, buffer.tobytes()

    async def capture_frame(self, session_id: str) -> Optional[bytes]:
        """Capture a single frame and return as JPEG bytes."""
        cap = self.active_cameras.get(session_id)
        if not cap:
            return None

        loop = asyncio.get_event_loop()
        success, frame_bytes = await loop.run_in_executor(
            _executor,
            self._read_frame,
            cap
        )

        if not success:
            logger.warning(f"Failed to capture frame for session {session_id}")
            return None

        return frame_bytes


# Global camera manager
camera_manager = CameraManager()


async def update_session_status(session_id: str, status: str):
    """Update session status in database."""
    async with async_session() as db:
        await db.execute(
            update(Session).where(Session.id == session_id).values(status=status)
        )
        await db.commit()


async def get_session_config(session_id: str, profile_id: str) -> Optional[dict]:
    """Get session configuration from database if owned by profile."""
    async with async_session() as db:
        result = await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.profile_id == profile_id
            )
        )
        session = result.scalar_one_or_none()
        if session:
            return {
                "source_type": session.source_type,
                "source_path": session.source_path,
                "resolution": session.video_resolution,
                "framerate": session.video_framerate,
            }
    return None


@router.websocket("/video/{session_id}")
async def video_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for live video streaming.

    Requires authentication via token query parameter.
    Sends JPEG frames as base64-encoded strings.
    """
    # Verify authentication before accepting connection
    if not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    profile_id = verify_ws_token(token)
    if not profile_id:
        await websocket.close(code=4001, reason="Invalid token")
        return

    # Get session config (also verifies ownership)
    config = await get_session_config(session_id, profile_id)
    if not config:
        await websocket.close(code=4004, reason="Session not found")
        return

    # Now accept the connection
    await websocket.accept()

    # Parse device index from source_path (e.g., "device:0")
    device_index = 0
    if config["source_path"] and config["source_path"].startswith("device:"):
        try:
            device_index = int(config["source_path"].split(":")[1])
        except (IndexError, ValueError):
            pass

    # Start camera capture
    resolution = config.get("resolution", "1080p")
    framerate = config.get("framerate", 30) or 30

    success = await camera_manager.start_capture(
        session_id,
        device_index=device_index,
        resolution=resolution,
        framerate=framerate
    )

    if not success:
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to open camera device {device_index}"
        })
        await websocket.close()
        return

    # Update session status to recording
    await update_session_status(session_id, "recording")

    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "device_index": device_index,
        "resolution": resolution,
        "framerate": framerate,
        "timestamp": datetime.utcnow().isoformat(),
    })

    # Calculate frame interval
    frame_interval = 1.0 / framerate
    frame_count = 0
    failed_frames = 0

    print(f"[VIDEO] Starting stream loop, interval={frame_interval:.3f}s")

    try:
        while True:
            start_time = asyncio.get_event_loop().time()

            # Capture frame
            frame_data = await camera_manager.capture_frame(session_id)

            if frame_data:
                frame_count += 1
                if frame_count == 1 or frame_count % 30 == 0:
                    print(f"[VIDEO] Sending frame {frame_count}, size={len(frame_data)} bytes")

                # Send frame as base64
                frame_b64 = base64.b64encode(frame_data).decode('utf-8')
                await websocket.send_json({
                    "type": "frame",
                    "data": frame_b64,
                    "timestamp_ms": int(datetime.utcnow().timestamp() * 1000),
                })
            else:
                failed_frames += 1
                if failed_frames <= 5 or failed_frames % 30 == 0:
                    print(f"[VIDEO] Frame capture failed (count: {failed_frames})")

            # Check for incoming messages (non-blocking)
            try:
                message = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=0.001
                )
                data = json.loads(message)
                if data.get("type") == "stop":
                    break
            except asyncio.TimeoutError:
                pass
            except json.JSONDecodeError:
                pass

            # Maintain framerate
            elapsed = asyncio.get_event_loop().time() - start_time
            sleep_time = max(0, frame_interval - elapsed)
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    except WebSocketDisconnect:
        print(f"[VIDEO] WebSocket disconnected after {frame_count} frames")
    except Exception as e:
        print(f"[VIDEO] Error in stream loop: {e}")
    finally:
        # Cleanup
        print(f"[VIDEO] Cleaning up, sent {frame_count} frames, {failed_frames} failed")
        await camera_manager.stop_capture(session_id)
        await update_session_status(session_id, "completed")
