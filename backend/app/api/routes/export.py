"""Export routes for session data."""
from __future__ import annotations

import csv
import json
import re
from datetime import datetime
from io import StringIO
from pathlib import Path
from typing import List

import aiofiles
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.auth import get_current_profile_id
from app.models.database import Session, Shot, Event, Foul, Game, KeyFrame
from app.models.schemas import ExportRequest, ExportResponse

router = APIRouter()


@router.post("/{session_id}", response_model=ExportResponse)
async def export_session(
    session_id: str,
    export_request: ExportRequest,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Export session data in specified format."""
    # Verify session exists and user owns it
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.profile_id == profile_id
        )
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Create export directory
    export_dir = settings.data_directory / "exports"
    export_dir.mkdir(exist_ok=True)

    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    format_type = export_request.format

    if format_type == "full_json":
        filename = f"session_{session_id}_{timestamp}_full.json"
        filepath = export_dir / filename
        await _export_full_json(session_id, filepath, db)

    elif format_type == "claude_json":
        filename = f"session_{session_id}_{timestamp}_claude.json"
        filepath = export_dir / filename
        await _export_claude_json(session_id, filepath, db)

    elif format_type == "shots_csv":
        filename = f"session_{session_id}_{timestamp}_shots.csv"
        filepath = export_dir / filename
        await _export_shots_csv(session_id, filepath, db)

    elif format_type == "events_jsonl":
        filename = f"session_{session_id}_{timestamp}_events.jsonl"
        filepath = export_dir / filename
        await _export_events_jsonl(session_id, filepath, db)

    else:
        raise HTTPException(status_code=400, detail=f"Unknown format: {format_type}")

    file_size = filepath.stat().st_size

    return ExportResponse(
        download_url=f"/api/export/download/{filename}",
        filename=filename,
        format=format_type,
        file_size_bytes=file_size,
    )


@router.get("/download/{filename}")
async def download_export(
    filename: str,
    profile_id: str = Depends(get_current_profile_id),
):
    """Download an exported file with path traversal protection."""
    # SECURITY: Validate filename format to prevent path traversal
    # Expected format: session_{hex32}_{YYYYMMDD}_{HHMMSS}_{type}.(json|csv|jsonl)
    if not re.match(r'^session_[a-f0-9]+_\d{8}_\d{6}_\w+\.(json|csv|jsonl)$', filename):
        raise HTTPException(status_code=400, detail="Invalid filename format")

    # SECURITY: Prevent path traversal sequences
    if '..' in filename or '/' in filename or '\\' in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    export_dir = settings.data_directory / "exports"
    filepath = (export_dir / filename).resolve()

    # SECURITY: Verify resolved path is within exports directory
    if not str(filepath).startswith(str(export_dir.resolve())):
        raise HTTPException(status_code=400, detail="Invalid path")

    if not filepath.exists():
        raise HTTPException(status_code=404, detail="Export file not found")

    # Determine media type
    if filename.endswith(".json"):
        media_type = "application/json"
    elif filename.endswith(".csv"):
        media_type = "text/csv"
    elif filename.endswith(".jsonl"):
        media_type = "application/x-ndjson"
    else:
        media_type = "application/octet-stream"

    return FileResponse(
        filepath,
        media_type=media_type,
        filename=filename,
    )


async def _export_full_json(session_id: str, filepath: Path, db: AsyncSession):
    """Export full session data including all related tables."""
    # Get session
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one()

    # Get all related data
    shots_result = await db.execute(select(Shot).where(Shot.session_id == session_id))
    events_result = await db.execute(select(Event).where(Event.session_id == session_id))
    fouls_result = await db.execute(select(Foul).where(Foul.session_id == session_id))
    games_result = await db.execute(select(Game).where(Game.session_id == session_id))
    frames_result = await db.execute(select(KeyFrame).where(KeyFrame.session_id == session_id))

    export_data = {
        "session": {
            "id": session.id,
            "name": session.name,
            "created_at": session.created_at.isoformat() if session.created_at else None,
            "started_at": session.started_at.isoformat() if session.started_at else None,
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "source_type": session.source_type,
            "total_shots": session.total_shots,
            "total_pocketed": session.total_pocketed,
            "total_fouls": session.total_fouls,
            "gemini_cost_usd": session.gemini_cost_usd,
        },
        "shots": [
            {
                "shot_number": s.shot_number,
                "timestamp_start_ms": s.timestamp_start_ms,
                "timestamp_end_ms": s.timestamp_end_ms,
                "balls_pocketed": s.balls_pocketed,
                "table_state_before": s.table_state_before,
                "table_state_after": s.table_state_after,
            }
            for s in shots_result.scalars().all()
        ],
        "events": [
            {
                "timestamp_ms": e.timestamp_ms,
                "event_type": e.event_type,
                "event_data": e.event_data,
            }
            for e in events_result.scalars().all()
        ],
        "fouls": [
            {
                "shot_number": f.shot_number,
                "timestamp_ms": f.timestamp_ms,
                "foul_type": f.foul_type,
                "details": f.details,
            }
            for f in fouls_result.scalars().all()
        ],
        "games": [
            {
                "game_number": g.game_number,
                "game_type": g.game_type,
                "winner": g.winner,
                "final_score": g.final_score,
            }
            for g in games_result.scalars().all()
        ],
        "key_frames": [
            {
                "timestamp_ms": kf.timestamp_ms,
                "frame_type": kf.frame_type,
                "file_path": kf.file_path,
            }
            for kf in frames_result.scalars().all()
        ],
    }

    async with aiofiles.open(filepath, "w") as f:
        await f.write(json.dumps(export_data, indent=2))


async def _export_claude_json(session_id: str, filepath: Path, db: AsyncSession):
    """Export AI-optimized session data."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one()

    shots_result = await db.execute(
        select(Shot).where(Shot.session_id == session_id).order_by(Shot.shot_number)
    )
    events_result = await db.execute(
        select(Event).where(Event.session_id == session_id).order_by(Event.timestamp_ms)
    )

    export_data = {
        "session_summary": {
            "total_shots": session.total_shots,
            "total_pocketed": session.total_pocketed,
            "total_fouls": session.total_fouls,
            "duration_ms": session.video_duration_ms,
        },
        "shots": [
            {
                "number": s.shot_number,
                "balls_pocketed": s.balls_pocketed or [],
                "table_before": s.table_state_before,
                "table_after": s.table_state_after,
            }
            for s in shots_result.scalars().all()
        ],
        "events": [
            {
                "t": e.timestamp_ms,
                "type": e.event_type,
                "data": e.event_data,
            }
            for e in events_result.scalars().all()
        ],
    }

    async with aiofiles.open(filepath, "w") as f:
        await f.write(json.dumps(export_data, indent=2))


async def _export_shots_csv(session_id: str, filepath: Path, db: AsyncSession):
    """Export shots as CSV."""
    shots_result = await db.execute(
        select(Shot).where(Shot.session_id == session_id).order_by(Shot.shot_number)
    )
    shots = shots_result.scalars().all()

    # Build CSV in memory then write asynchronously
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "shot_number", "game_number", "timestamp_start_ms", "timestamp_end_ms",
        "duration_ms", "balls_pocketed", "confidence"
    ])

    for shot in shots:
        pocketed = ",".join(shot.balls_pocketed) if shot.balls_pocketed else ""
        writer.writerow([
            shot.shot_number,
            shot.game_number,
            shot.timestamp_start_ms,
            shot.timestamp_end_ms,
            shot.duration_ms,
            pocketed,
            shot.confidence_overall,
        ])

    async with aiofiles.open(filepath, "w", newline="") as f:
        await f.write(output.getvalue())


async def _export_events_jsonl(session_id: str, filepath: Path, db: AsyncSession):
    """Export events as JSON Lines."""
    events_result = await db.execute(
        select(Event).where(Event.session_id == session_id).order_by(Event.timestamp_ms)
    )
    events = events_result.scalars().all()

    # Build JSONL content in memory then write asynchronously
    lines = []
    for event in events:
        line = json.dumps({
            "timestamp_ms": event.timestamp_ms,
            "event_type": event.event_type,
            "event_data": event.event_data,
        })
        lines.append(line)

    async with aiofiles.open(filepath, "w") as f:
        await f.write("\n".join(lines) + "\n" if lines else "")
