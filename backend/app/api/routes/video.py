"""Video upload and streaming routes."""
from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, BackgroundTasks
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.models.database import Session
from app.models.schemas import GoProConfig, VideoUploadResponse, StreamInfo

router = APIRouter()


async def process_video_to_hls(video_path: Path, session_id: str):
    """Background task: Convert video to HLS segments using FFmpeg."""
    hls_dir = settings.data_directory / "hls" / session_id
    hls_dir.mkdir(parents=True, exist_ok=True)

    playlist_path = hls_dir / "stream.m3u8"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-c:a", "aac",
        "-b:a", "128k",
        "-start_number", "0",
        "-hls_time", str(settings.hls_segment_duration),
        "-hls_list_size", "0",
        "-hls_segment_filename", str(hls_dir / "segment_%03d.ts"),
        "-f", "hls",
        str(playlist_path)
    ]

    process = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    await process.wait()


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db)
):
    """Upload a video file for processing."""
    # Validate file type
    allowed_extensions = {".mp4", ".mov", ".mkv", ".avi", ".m4v"}
    file_ext = Path(file.filename).suffix.lower()

    if file_ext not in allowed_extensions:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )

    # Create or get session
    if not session_id:
        session_id = uuid.uuid4().hex
        session = Session(
            id=session_id,
            name=file.filename,
            source_type="video_file",
            source_path=file.filename,
            status="processing",
        )
        db.add(session)
        await db.commit()
    else:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")

    # Save uploaded file
    upload_dir = settings.data_directory / "uploads" / session_id
    upload_dir.mkdir(parents=True, exist_ok=True)
    video_path = upload_dir / f"source{file_ext}"

    file_size = 0
    async with aiofiles.open(video_path, "wb") as f:
        while chunk := await file.read(1024 * 1024):  # 1MB chunks
            await f.write(chunk)
            file_size += len(chunk)

    # Update session with file info
    session.source_path = str(video_path)
    await db.commit()

    # Start HLS conversion in background
    if background_tasks:
        background_tasks.add_task(process_video_to_hls, video_path, session_id)

    stream_url = f"/hls/{session_id}/stream.m3u8"

    return VideoUploadResponse(
        session_id=session_id,
        filename=file.filename,
        file_size_bytes=file_size,
        duration_ms=None,  # Will be available after processing
        stream_url=stream_url,
    )


@router.get("/stream/{session_id}", response_model=StreamInfo)
async def get_stream_info(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get HLS stream information for a session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    hls_path = settings.data_directory / "hls" / session_id / "stream.m3u8"
    status = "ready" if hls_path.exists() else "processing"

    return StreamInfo(
        session_id=session_id,
        stream_url=f"/hls/{session_id}/stream.m3u8",
        status=status,
        duration_ms=session.video_duration_ms,
    )


@router.post("/gopro/test")
async def test_gopro_connection(config: GoProConfig):
    """Test GoPro connection without creating a session."""
    import socket
    import cv2

    if config.connection_mode == "wifi":
        if not config.wifi_ip:
            return {"success": False, "message": "WiFi IP address required"}

        # Try to connect to the GoPro IP
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)  # 3 second timeout
            result = sock.connect_ex((config.wifi_ip, config.wifi_port))
            sock.close()

            if result == 0:
                return {
                    "success": True,
                    "message": f"GoPro found at {config.wifi_ip}:{config.wifi_port}",
                    "device": {
                        "ip": config.wifi_ip,
                        "port": config.wifi_port,
                        "protocol": config.protocol,
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"Cannot reach {config.wifi_ip}:{config.wifi_port}. Is the GoPro WiFi on?"
                }
        except socket.timeout:
            return {"success": False, "message": f"Connection timed out. Check GoPro WiFi."}
        except Exception as e:
            return {"success": False, "message": f"Connection error: {str(e)}"}

    else:  # USB mode
        # Enumerate USB cameras using OpenCV
        available_cameras = []
        for i in range(10):  # Check first 10 device indices
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                # Get camera info
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                available_cameras.append({
                    "index": i,
                    "resolution": f"{width}x{height}",
                })
                cap.release()

        if available_cameras:
            return {
                "success": True,
                "message": f"Found {len(available_cameras)} camera(s)",
                "devices": available_cameras,
            }
        else:
            return {
                "success": False,
                "message": "No USB cameras detected. Connect your GoPro via USB.",
            }


@router.post("/gopro/connect")
async def connect_gopro(
    config: GoProConfig,
    db: AsyncSession = Depends(get_db)
):
    """Initialize GoPro connection and return stream URL."""
    # Create session for GoPro stream
    session_id = uuid.uuid4().hex

    if config.connection_mode == "wifi":
        if not config.wifi_ip:
            raise HTTPException(status_code=400, detail="WiFi IP required for WiFi mode")

        # Build stream URL based on protocol
        if config.protocol == "udp":
            source_url = f"udp://{config.wifi_ip}:{config.wifi_port}"
        elif config.protocol == "rtsp":
            source_url = f"rtsp://{config.wifi_ip}:{config.wifi_port}/live"
        else:  # http
            source_url = f"http://{config.wifi_ip}:{config.wifi_port}/live/amba.m3u8"

        source_type = "gopro_wifi"
    else:
        # USB mode - would use device index
        source_url = "device:0"
        source_type = "gopro_usb"

    session = Session(
        id=session_id,
        name=f"GoPro Live - {config.resolution}@{config.framerate}fps",
        source_type=source_type,
        source_path=source_url,
        video_resolution=config.resolution,
        video_framerate=config.framerate,
        status="pending",
    )

    db.add(session)
    await db.commit()

    return {
        "session_id": session_id,
        "source_url": source_url,
        "stream_url": f"/ws/video/{session_id}",
        "status": "ready",
    }


@router.get("/thumbnail/{session_id}")
async def get_thumbnail(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get session thumbnail image."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check for thumbnail
    thumbnail_path = settings.data_directory / "sessions" / session_id / "thumbnail.jpg"

    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    return FileResponse(thumbnail_path, media_type="image/jpeg")
