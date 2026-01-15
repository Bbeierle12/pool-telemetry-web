"""Event retrieval routes."""
from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.database import Event, Session
from app.models.schemas import EventResponse

router = APIRouter()


@router.get("/{session_id}", response_model=List[EventResponse])
async def list_events(
    session_id: str,
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    db: AsyncSession = Depends(get_db)
):
    """List events for a session."""
    # Verify session exists
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Query events
    query = select(Event).where(Event.session_id == session_id)

    if event_type:
        query = query.where(Event.event_type == event_type)

    query = query.order_by(Event.timestamp_ms).offset(skip).limit(limit)

    result = await db.execute(query)
    events = result.scalars().all()

    return events


@router.get("/{session_id}/types")
async def list_event_types(
    session_id: str,
    db: AsyncSession = Depends(get_db)
):
    """List unique event types in a session."""
    result = await db.execute(
        select(Event.event_type)
        .where(Event.session_id == session_id)
        .distinct()
    )
    types = [row[0] for row in result.all()]

    return {"session_id": session_id, "event_types": types}


@router.get("/{session_id}/latest")
async def get_latest_events(
    session_id: str,
    count: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db)
):
    """Get the most recent events for a session."""
    result = await db.execute(
        select(Event)
        .where(Event.session_id == session_id)
        .order_by(Event.timestamp_ms.desc())
        .limit(count)
    )
    events = result.scalars().all()

    # Return in chronological order
    return list(reversed(events))
