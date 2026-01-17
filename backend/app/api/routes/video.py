"""Video upload and streaming routes."""
import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db, async_session
from app.core.auth import get_current_profile_id
from app.core.rate_limit import limiter, RATE_LIMIT_UPLOAD
from app.models.database import Session
from app.models.schemas import GoProConfig, VideoUploadResponse, StreamInfo

router = APIRouter()
logger = logging.getLogger(__name__)


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
    stdout, stderr = await process.communicate()

    # Update session status based on FFmpeg result
    async with async_session() as db:
        result = await db.execute(select(Session).where(Session.id == session_id))
        session = result.scalar_one_or_none()
        if session:
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown FFmpeg error"
                logger.error(f"FFmpeg failed for session {session_id}: {error_msg}")
                session.status = "error"
                session.notes = f"FFmpeg error: {error_msg[:500]}"
            else:
                logger.info(f"FFmpeg completed successfully for session {session_id}")
                session.status = "ready"
            await db.commit()


@router.post("/upload", response_model=VideoUploadResponse)
@limiter.limit(RATE_LIMIT_UPLOAD)
async def upload_video(
    request: Request,
    background_tasks: BackgroundTasks,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db),
    file: UploadFile = File(...),
    session_id: Optional[str] = None,
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
            profile_id=profile_id,
            name=file.filename,
            source_type="video_file",
            source_path=file.filename,
            status="processing",
        )
        db.add(session)
        await db.commit()
    else:
        result = await db.execute(
            select(Session).where(
                Session.id == session_id,
                Session.profile_id == profile_id
            )
        )
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
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get HLS stream information for a session."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.profile_id == profile_id
        )
    )
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
    profile_id: str = Depends(get_current_profile_id),
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
        # USB mode - use device index from config
        device_index = config.device_index if config.device_index is not None else 0
        source_url = f"device:{device_index}"
        source_type = "gopro_usb"

    session = Session(
        id=session_id,
        profile_id=profile_id,
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
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get session thumbnail image."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.profile_id == profile_id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check for thumbnail
    thumbnail_path = settings.data_directory / "sessions" / session_id / "thumbnail.jpg"

    if not thumbnail_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not available")

    return FileResponse(thumbnail_path, media_type="image/jpeg")
