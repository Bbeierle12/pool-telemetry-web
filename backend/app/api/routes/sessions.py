"""Session management routes."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.database import Session, Shot, Event, Foul, Game, KeyFrame
from app.models.schemas import (
    SessionCreate, SessionResponse, SessionSummary, SessionUpdate
)

router = APIRouter()


@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    session_data: SessionCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new recording session."""
    session_id = uuid.uuid4().hex
    now = datetime.utcnow()

    session = Session(
        id=session_id,
        name=session_data.name or f"Session {now.strftime('%Y-%m-%d %H:%M')}",
        source_type=session_data.source_type,
        source_path=session_data.source_path,
        status="pending",
        created_at=now,
    )

    db.add(session)
    await db.commit()
    await db.refresh(session)

    return session


@router.get("/", response_model=List[SessionSummary])
async def list_sessions(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db)
):
    """List all sessions with pagination."""
    query = select(Session).order_by(Session.created_at.desc())

    if status_filter:
        query = query.where(Session.status == status_filter)

    query = query.offset(skip).limit(limit)
    result = await db.execute(query)
    sessions = result.scalars().all()

    # Calculate duration for each session
    summaries = []
    for session in sessions:
        duration = None
        if session.started_at and session.ended_at:
            duration = int((session.ended_at - session.started_at).total_seconds())

        summaries.append(SessionSummary(
            id=session.id,
            name=session.name,
            created_at=session.created_at,
            status=session.status,
            source_type=session.source_type,
            total_shots=session.total_shots,
            total_pocketed=session.total_pocketed,
            total_fouls=session.total_fouls,
            duration_seconds=duration,
        ))

    return summaries


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed session information."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    return session


@router.patch("/{session_id}", response_model=SessionResponse)
async def update_session(
    session_id: str,
    updates: SessionUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update session fields."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Apply updates
    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(session, field, value)

    # Handle status transitions
    if updates.status == "recording" and not session.started_at:
        session.started_at = datetime.utcnow()
    elif updates.status == "completed" and not session.ended_at:
        session.ended_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    return session


@router.post("/{session_id}/start", response_model=SessionResponse)
async def start_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Start recording a session."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    session.status = "recording"
    session.started_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    return session


@router.post("/{session_id}/stop", response_model=SessionResponse)
async def stop_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Stop recording a session."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    session.status = "completed"
    session.ended_at = datetime.utcnow()

    await db.commit()
    await db.refresh(session)

    return session


@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Delete a session and all related data."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Cascade delete handles related records
    await db.delete(session)
    await db.commit()

    return {"status": "deleted", "session_id": session_id}


@router.get("/{session_id}/stats")
async def get_session_stats(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Get detailed statistics for a session."""
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found"
        )

    # Count related records
    shots_result = await db.execute(
        select(Shot).where(Shot.session_id == session_id)
    )
    shots = shots_result.scalars().all()

    events_result = await db.execute(
        select(Event).where(Event.session_id == session_id)
    )
    events_count = len(events_result.scalars().all())

    return {
        "session_id": session_id,
        "total_shots": len(shots),
        "total_pocketed": session.total_pocketed,
        "total_fouls": session.total_fouls,
        "total_events": events_count,
        "gemini_cost_usd": session.gemini_cost_usd,
        "duration_ms": session.video_duration_ms,
    }
