"""Analysis routes for shots and sessions."""
from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.database import get_db
from app.core.auth import get_current_profile_id
from app.api.websockets.events import broadcast_event, broadcast_foul, broadcast_pocket, broadcast_shot
from app.models.database import Event, Foul, PhysicsAnalysis, Session, Shot, Trajectory
from app.models.schemas import (
    PrototypeAnalysisRequest,
    PrototypeAnalysisResponse,
    ShotDetail,
    ShotResponse,
)
from app.services.prototype_scoring import OpenCVPoolPrototypeAnalyzer, PrototypeDetectedEvent

router = APIRouter()


async def _verify_session_ownership(
    session_id: str,
    profile_id: str,
    db: AsyncSession
) -> Session:
    """Verify session exists and belongs to the profile."""
    result = await db.execute(
        select(Session).where(
            Session.id == session_id,
            Session.profile_id == profile_id
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


async def _delete_existing_analysis(session_id: str, db: AsyncSession) -> None:
    """Delete previously generated analysis records for a session."""
    await db.execute(delete(Foul).where(Foul.session_id == session_id))
    await db.execute(delete(Event).where(Event.session_id == session_id))
    await db.execute(delete(Shot).where(Shot.session_id == session_id))


async def _broadcast_detected_event(session_id: str, event: PrototypeDetectedEvent) -> None:
    """Fan out a detected event without duplicating database rows."""
    event_type = event.event_type.lower()

    if event_type == "shot":
        await broadcast_shot(session_id, event.event_data)
        return

    if event_type == "pocket":
        await broadcast_pocket(
            session_id,
            event.event_data.get("ball", "unknown_ball"),
            event.event_data.get("pocket", "unknown_pocket"),
        )
        return

    if event_type == "foul":
        await broadcast_foul(
            session_id,
            event.event_data.get("foul_type", "unknown_foul"),
            event.event_data.get("details", event.event_data),
        )
        return

    await broadcast_event(session_id, event.event_type, event.event_data)


@router.get("/{session_id}/shots", response_model=List[ShotResponse])
async def list_shots(
    session_id: str,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """List all shots in a session."""
    await _verify_session_ownership(session_id, profile_id, db)

    shots_result = await db.execute(
        select(Shot)
        .where(Shot.session_id == session_id)
        .order_by(Shot.shot_number)
        .offset(skip)
        .limit(limit)
    )
    shots = shots_result.scalars().all()

    return shots


@router.get("/{session_id}/shots/{shot_number}", response_model=ShotDetail)
async def get_shot_detail(
    session_id: str,
    shot_number: int,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get detailed information for a specific shot."""
    await _verify_session_ownership(session_id, profile_id, db)

    result = await db.execute(
        select(Shot)
        .where(Shot.session_id == session_id)
        .where(Shot.shot_number == shot_number)
    )
    shot = result.scalar_one_or_none()

    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    return shot


@router.get("/{session_id}/shots/{shot_number}/physics")
async def get_shot_physics(
    session_id: str,
    shot_number: int,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get physics analysis for a shot."""
    await _verify_session_ownership(session_id, profile_id, db)

    shot_result = await db.execute(
        select(Shot)
        .where(Shot.session_id == session_id)
        .where(Shot.shot_number == shot_number)
    )
    shot = shot_result.scalar_one_or_none()

    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    physics_result = await db.execute(
        select(PhysicsAnalysis).where(PhysicsAnalysis.shot_id == shot.id)
    )
    physics = physics_result.scalar_one_or_none()

    if not physics:
        return {"message": "Physics analysis not available for this shot"}

    return {
        "shot_number": shot_number,
        "cue_initial_speed": physics.cue_initial_speed,
        "cue_initial_speed_mph": physics.cue_initial_speed_mph,
        "cue_initial_angle": physics.cue_initial_angle,
        "cue_distance_traveled": physics.cue_distance_traveled,
        "total_collisions": physics.total_collisions,
        "energy_efficiency": physics.energy_efficiency,
        "physics_valid": physics.physics_valid,
        "validation_errors": physics.validation_errors,
    }


@router.get("/{session_id}/shots/{shot_number}/trajectories")
async def get_shot_trajectories(
    session_id: str,
    shot_number: int,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get ball trajectories for a shot."""
    await _verify_session_ownership(session_id, profile_id, db)

    shot_result = await db.execute(
        select(Shot)
        .where(Shot.session_id == session_id)
        .where(Shot.shot_number == shot_number)
    )
    shot = shot_result.scalar_one_or_none()

    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    traj_result = await db.execute(
        select(Trajectory).where(Trajectory.shot_id == shot.id)
    )
    trajectories = traj_result.scalars().all()

    return {
        "shot_number": shot_number,
        "trajectories": [
            {
                "ball_name": t.ball_name,
                "points": t.points,
                "total_distance": t.total_distance,
                "max_speed": t.max_speed,
            }
            for t in trajectories
        ]
    }


@router.get("/{session_id}/accuracy")
async def get_accuracy_stats(
    session_id: str,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get accuracy statistics for a session."""
    session = await _verify_session_ownership(session_id, profile_id, db)

    # Get total shot count using SQL COUNT
    total_shots = await db.scalar(
        select(func.count()).select_from(Shot).where(Shot.session_id == session_id)
    ) or 0

    if total_shots == 0:
        return {
            "session_id": session_id,
            "total_shots": 0,
            "accuracy_rate": 0.0,
            "avg_balls_per_shot": 0.0,
        }

    # For accuracy calculations, we need to load shots with pocketed data
    # This is necessary because balls_pocketed is a JSON field
    shots_result = await db.execute(
        select(Shot.balls_pocketed).where(Shot.session_id == session_id)
    )
    balls_pocketed_list = [row[0] for row in shots_result.all()]

    shots_with_pockets = sum(
        1 for bp in balls_pocketed_list if bp and len(bp) > 0
    )
    total_pocketed = sum(
        len(bp) for bp in balls_pocketed_list if bp
    )

    return {
        "session_id": session_id,
        "total_shots": total_shots,
        "successful_shots": shots_with_pockets,
        "accuracy_rate": shots_with_pockets / total_shots if total_shots > 0 else 0.0,
        "total_balls_pocketed": total_pocketed,
        "avg_balls_per_shot": total_pocketed / total_shots if total_shots > 0 else 0.0,
        "fouls": session.total_fouls,
        "foul_rate": session.total_fouls / total_shots if total_shots > 0 else 0.0,
    }


@router.get("/{session_id}/breakdown")
async def get_shot_breakdown(
    session_id: str,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db)
):
    """Get shot breakdown by type and outcome."""
    await _verify_session_ownership(session_id, profile_id, db)

    # Get total count
    total_shots = await db.scalar(
        select(func.count()).select_from(Shot).where(Shot.session_id == session_id)
    ) or 0

    # Get balls_pocketed data for outcome analysis
    shots_result = await db.execute(
        select(Shot.balls_pocketed).where(Shot.session_id == session_id)
    )
    balls_pocketed_list = [row[0] for row in shots_result.all()]

    # Analyze shot outcomes
    outcomes = {
        "successful": 0,
        "missed": 0,
        "foul": 0,
    }

    for bp in balls_pocketed_list:
        if bp and len(bp) > 0:
            outcomes["successful"] += 1
        else:
            outcomes["missed"] += 1

    return {
        "session_id": session_id,
        "total_shots": total_shots,
        "outcomes": outcomes,
    }


@router.post("/{session_id}/prototype", response_model=PrototypeAnalysisResponse)
async def run_prototype_analysis(
    session_id: str,
    request: PrototypeAnalysisRequest,
    profile_id: str = Depends(get_current_profile_id),
    db: AsyncSession = Depends(get_db),
):
    """Run the local OpenCV prototype scorer against an uploaded session video."""
    session = await _verify_session_ownership(session_id, profile_id, db)

    if not session.source_path:
        raise HTTPException(status_code=400, detail="Session has no source video path to analyze")

    video_path = Path(session.source_path)
    if not video_path.is_file():
        raise HTTPException(
            status_code=400,
            detail="Prototype analysis currently supports uploaded or local video files only",
        )

    if not request.replace_existing:
        existing_rows = (
            (await db.scalar(select(func.count()).select_from(Shot).where(Shot.session_id == session_id))) or 0
        ) + (
            (await db.scalar(select(func.count()).select_from(Event).where(Event.session_id == session_id))) or 0
        ) + (
            (await db.scalar(select(func.count()).select_from(Foul).where(Foul.session_id == session_id))) or 0
        )
        if existing_rows > 0:
            raise HTTPException(
                status_code=409,
                detail="Session already contains analysis data. Re-run with replace_existing=true to overwrite it.",
            )

    analyzer = OpenCVPoolPrototypeAnalyzer(
        sample_fps=request.sample_fps or settings.prototype_analysis_fps,
        max_frames=request.max_frames or settings.prototype_max_frames,
    )

    try:
        result = analyzer.analyze(video_path)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if request.replace_existing:
        await _delete_existing_analysis(session_id, db)

    for shot in result.shots:
        db.add(
            Shot(
                session_id=session_id,
                shot_number=shot.shot_number,
                game_number=1,
                timestamp_start_ms=shot.timestamp_start_ms,
                timestamp_end_ms=shot.timestamp_end_ms,
                duration_ms=shot.duration_ms,
                table_state_before=shot.table_state_before,
                table_state_after=shot.table_state_after,
                balls_pocketed=shot.balls_pocketed,
                analyzed=True,
                analysis_data={
                    **shot.analysis_data,
                    "foul_types": shot.foul_types,
                    "source": "opencv_prototype",
                },
                derived_metrics={
                    "foul_count": len(shot.foul_types),
                    "pocketed_count": len(shot.balls_pocketed),
                },
                confidence_overall=shot.confidence_overall,
            )
        )

    for event in result.events:
        db.add(
            Event(
                session_id=session_id,
                timestamp_ms=event.timestamp_ms,
                event_type=event.event_type,
                event_data=event.event_data,
                processed=True,
            )
        )

        if event.event_type != "foul":
            continue

        foul_details = event.event_data.get("details", {})
        db.add(
            Foul(
                session_id=session_id,
                shot_number=event.event_data.get("shot_number"),
                timestamp_ms=event.timestamp_ms,
                foul_type=event.event_data.get("foul_type"),
                details=foul_details,
            )
        )

    session.total_shots = len(result.shots)
    session.total_pocketed = sum(len(shot.balls_pocketed) for shot in result.shots)
    session.total_fouls = result.fouls_detected
    session.video_duration_ms = max(session.video_duration_ms or 0, result.duration_ms)
    session.extra_data = {
        **(session.extra_data or {}),
        "prototype_analysis": {
            "analyzed_frames": result.analyzed_frames,
            "sample_fps": result.sample_fps,
            "duration_ms": result.duration_ms,
            "shots_detected": len(result.shots),
            "pockets_detected": result.pockets_detected,
            "fouls_detected": result.fouls_detected,
            "notes": result.notes,
            "frame_size": {
                "width": result.frame_width,
                "height": result.frame_height,
            },
            "source": "opencv_prototype",
        },
    }

    await db.commit()
    await db.refresh(session)

    for event in result.events:
        await _broadcast_detected_event(session_id, event)

    return PrototypeAnalysisResponse(
        session_id=session_id,
        status="completed",
        analyzed_frames=result.analyzed_frames,
        sample_fps=result.sample_fps,
        shots_detected=len(result.shots),
        pockets_detected=result.pockets_detected,
        fouls_detected=result.fouls_detected,
        duration_ms=result.duration_ms,
        notes=result.notes,
        session=session,
    )
