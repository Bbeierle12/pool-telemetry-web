"""Analysis routes for shots and sessions."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.auth import get_current_profile_id
from app.models.database import Session, Shot, PhysicsAnalysis, Trajectory
from app.models.schemas import ShotResponse, ShotDetail

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
