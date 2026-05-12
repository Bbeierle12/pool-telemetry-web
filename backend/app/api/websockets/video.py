"""WebSocket handler for live video streaming."""
from __future__ import annotations

import asyncio
import base64
import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

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
    """Manage USB camera and network stream capture."""

    def __init__(self):
        self.active_cameras: Dict[str, cv2.VideoCapture] = {}
        self._lock = asyncio.Lock()

    def _open_usb_camera(
        self,
        device_index: int,
        resolution: str,
        framerate: int
    ) -> Optional[cv2.VideoCapture]:
        """Open USB camera (runs in thread pool)."""
        print(f"[VIDEO] Attempting to open USB camera {device_index}")

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

    def _open_network_stream(
        self,
        stream_url: str,
        resolution: str,
        framerate: int
    ) -> Optional[cv2.VideoCapture]:
        """Open network stream (UDP, RTSP, HTTP) - runs in thread pool."""
        print(f"[VIDEO] Attempting to open network stream: {stream_url}")

        # Set environment variables for better UDP/RTSP handling
        import os
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;udp|buffer_size;65536"

        # For UDP streams, OpenCV needs specific format
        # GoPro Hero 7 uses UDP multicast
        cap = cv2.VideoCapture(stream_url, cv2.CAP_FFMPEG)

        if not cap or not cap.isOpened():
            print(f"[VIDEO] Failed to open stream with FFMPEG, trying default...")
            cap = cv2.VideoCapture(stream_url)

        if not cap or not cap.isOpened():
            print(f"[VIDEO] Failed to open network stream: {stream_url}")
            return None

        # Set buffer size for lower latency
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        # Read actual settings
        actual_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        actual_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        actual_fps = cap.get(cv2.CAP_PROP_FPS)
        print(f"[VIDEO] Network stream opened: {actual_w}x{actual_h} @ {actual_fps}fps")

        # Test read a frame (with timeout for network streams)
        ret, frame = cap.read()
        if ret and frame is not None:
            print(f"[VIDEO] Test frame captured from stream: {frame.shape}")
        else:
            print(f"[VIDEO] WARNING: Test frame capture failed - stream may need time to start")

        return cap

    async def start_capture(
        self,
        session_id: str,
        source: str,
        resolution: str = "1080p",
        framerate: int = 30
    ) -> bool:
        """Start capturing from USB camera or network stream.

        Args:
            session_id: Unique session identifier
            source: Either "device:N" for USB or a URL (udp://, rtsp://, http://)
            resolution: Video resolution (720p, 1080p, etc.)
            framerate: Target framerate
        """
        async with self._lock:
            if session_id in self.active_cameras:
                return True  # Already capturing

            loop = asyncio.get_event_loop()

            # Determine source type
            if source.startswith("device:"):
                # USB camera
                try:
                    device_index = int(source.split(":")[1])
                except (IndexError, ValueError):
                    device_index = 0

                cap = await loop.run_in_executor(
                    _executor,
                    self._open_usb_camera,
                    device_index,
                    resolution,
                    framerate
                )
            elif source.startswith(("udp://", "rtsp://", "http://", "https://")):
                # Network stream
                cap = await loop.run_in_executor(
                    _executor,
                    self._open_network_stream,
                    source,
                    resolution,
                    framerate
                )
            else:
                print(f"[VIDEO] Unknown source type: {source}")
                return False

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


class MobileVideoSession:
    """Track connected clients for a mobile camera video session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.producer: Optional[WebSocket] = None
        self.consumers: List[WebSocket] = []
        self.frame_count = 0

    async def broadcast_to_consumers(self, message: dict):
        """Send message to all connected consumers."""
        disconnected = []
        for consumer in self.consumers:
            try:
                await consumer.send_json(message)
            except Exception:
                disconnected.append(consumer)

        # Remove disconnected consumers
        for ws in disconnected:
            if ws in self.consumers:
                self.consumers.remove(ws)


# Global mobile video sessions
mobile_video_sessions: Dict[str, MobileVideoSession] = {}


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


async def handle_mobile_camera_session(
    websocket: WebSocket,
    session_id: str,
    config: dict
):
    """Handle mobile camera session - relay frames from mobile producer to desktop consumers."""
    await websocket.accept()

    # Get or create video session
    if session_id not in mobile_video_sessions:
        mobile_video_sessions[session_id] = MobileVideoSession(session_id)

    vs = mobile_video_sessions[session_id]
    is_producer = False

    try:
        # Wait for role identification message (with timeout)
        try:
            role_msg = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=30.0
            )
        except asyncio.TimeoutError:
            await websocket.send_json({
                "type": "error",
                "message": "Timeout waiting for role registration"
            })
            return

        if role_msg.get("type") == "register_producer":
            # Mobile client - becomes the frame producer
            if vs.producer is not None:
                await websocket.send_json({
                    "type": "error",
                    "message": "Producer already connected. Only one mobile device allowed."
                })
                return

            vs.producer = websocket
            is_producer = True
            print(f"[MOBILE] Producer registered for session {session_id}")

            await websocket.send_json({
                "type": "registered",
                "role": "producer",
                "session_id": session_id,
            })

            # Notify existing consumers that producer is now connected
            await vs.broadcast_to_consumers({
                "type": "producer_connected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

            # Update session status
            await update_session_status(session_id, "recording")

            # Frame relay loop - receive frames from producer and broadcast to consumers
            while True:
                message = await websocket.receive_json()

                if message.get("type") == "frame":
                    vs.frame_count += 1
                    if vs.frame_count == 1 or vs.frame_count % 100 == 0:
                        print(f"[MOBILE] Relaying frame {vs.frame_count} to {len(vs.consumers)} consumers")

                    # Relay frame to all consumers
                    await vs.broadcast_to_consumers(message)

                elif message.get("type") == "stop":
                    break

        elif role_msg.get("type") == "register_consumer":
            # Desktop client - becomes a frame consumer
            vs.consumers.append(websocket)
            print(f"[MOBILE] Consumer registered for session {session_id}, total: {len(vs.consumers)}")

            await websocket.send_json({
                "type": "registered",
                "role": "consumer",
                "session_id": session_id,
                "producer_connected": vs.producer is not None,
                "frame_count": vs.frame_count,
            })

            # Keep connection alive and wait for disconnect or messages
            while True:
                try:
                    message = await websocket.receive_json()
                    if message.get("type") == "stop":
                        break
                except Exception:
                    break

        else:
            await websocket.send_json({
                "type": "error",
                "message": f"Unknown role type: {role_msg.get('type')}. Expected 'register_producer' or 'register_consumer'"
            })

    except WebSocketDisconnect:
        print(f"[MOBILE] WebSocket disconnected (producer={is_producer})")
    except Exception as e:
        print(f"[MOBILE] Error in mobile camera session: {e}")
    finally:
        # Cleanup
        if is_producer:
            vs.producer = None
            print(f"[MOBILE] Producer disconnected, notifying {len(vs.consumers)} consumers")
            await vs.broadcast_to_consumers({
                "type": "producer_disconnected",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            await update_session_status(session_id, "completed")
        else:
            if websocket in vs.consumers:
                vs.consumers.remove(websocket)
            print(f"[MOBILE] Consumer disconnected, remaining: {len(vs.consumers)}")

        # Clean up session if no one is connected
        if vs.producer is None and len(vs.consumers) == 0:
            if session_id in mobile_video_sessions:
                del mobile_video_sessions[session_id]
                print(f"[MOBILE] Session {session_id} cleaned up")


@router.websocket("/video/{session_id}")
async def video_websocket(
    websocket: WebSocket,
    session_id: str,
    token: Optional[str] = Query(None),
):
    """
    WebSocket endpoint for live video streaming.

    Requires authentication via token query parameter.
    For mobile_camera sessions: Supports producer/consumer frame relay.
    For other sessions: Captures from camera and sends frames.
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

    # Route based on source type
    source_type = config.get("source_type", "gopro_usb")

    if source_type == "mobile_camera":
        # Handle mobile camera sessions with producer/consumer pattern
        await handle_mobile_camera_session(websocket, session_id, config)
        return

    # Now accept the connection for regular camera capture
    await websocket.accept()

    # Get source path - can be "device:N" for USB or a URL for WiFi streams
    source_path = config.get("source_path") or "device:0"
    resolution = config.get("resolution", "1080p")
    framerate = config.get("framerate", 30) or 30

    print(f"[VIDEO] Starting capture - source: {source_path}, type: {source_type}")

    # Start capture (works for both USB and network streams)
    success = await camera_manager.start_capture(
        session_id,
        source=source_path,
        resolution=resolution,
        framerate=framerate
    )

    if not success:
        await websocket.send_json({
            "type": "error",
            "message": f"Failed to open video source: {source_path}"
        })
        await websocket.close()
        return

    # Update session status to recording
    await update_session_status(session_id, "recording")

    # Send connection confirmation
    await websocket.send_json({
        "type": "connected",
        "session_id": session_id,
        "source": source_path,
        "source_type": source_type,
        "resolution": resolution,
        "framerate": framerate,
        "timestamp": datetime.now(timezone.utc).isoformat(),
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
                    "timestamp_ms": int(datetime.now(timezone.utc).timestamp() * 1000),
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
