"""API integration tests for events endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Session, Event


class TestEventListing:
    """Tests for event listing endpoints."""

    @pytest.mark.asyncio
    async def test_list_events_empty_session(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id} should return empty list for new session."""
        # Create a session directly
        session = Session(id="test-session-1", name="Test", source_type="video_file", status="pending")
        test_db.add(session)
        await test_db.commit()

        response = await client.get("/api/events/test-session-1")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_events_with_data(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id} should return events in chronological order."""
        # Create session and events
        session = Session(id="test-session-2", name="Test", source_type="video_file", status="recording")
        test_db.add(session)

        events = [
            Event(session_id="test-session-2", timestamp_ms=100, event_type="shot"),
            Event(session_id="test-session-2", timestamp_ms=200, event_type="pocket"),
            Event(session_id="test-session-2", timestamp_ms=300, event_type="shot"),
        ]
        for e in events:
            test_db.add(e)
        await test_db.commit()

        response = await client.get("/api/events/test-session-2")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3
        assert data[0]["timestamp_ms"] == 100
        assert data[2]["timestamp_ms"] == 300

    @pytest.mark.asyncio
    async def test_list_events_filter_by_type(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id}?event_type=X should filter events."""
        session = Session(id="test-session-3", name="Test", source_type="video_file", status="recording")
        test_db.add(session)

        events = [
            Event(session_id="test-session-3", timestamp_ms=100, event_type="shot"),
            Event(session_id="test-session-3", timestamp_ms=200, event_type="pocket"),
            Event(session_id="test-session-3", timestamp_ms=300, event_type="shot"),
        ]
        for e in events:
            test_db.add(e)
        await test_db.commit()

        response = await client.get("/api/events/test-session-3?event_type=shot")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert all(e["event_type"] == "shot" for e in data)

    @pytest.mark.asyncio
    async def test_list_events_pagination(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id} should support pagination."""
        session = Session(id="test-session-4", name="Test", source_type="video_file", status="recording")
        test_db.add(session)

        # Create 10 events
        for i in range(10):
            test_db.add(Event(
                session_id="test-session-4",
                timestamp_ms=i * 100,
                event_type="shot"
            ))
        await test_db.commit()

        # Get first 3
        response = await client.get("/api/events/test-session-4?limit=3")
        assert len(response.json()) == 3

        # Get next 3
        response = await client.get("/api/events/test-session-4?skip=3&limit=3")
        data = response.json()
        assert len(data) == 3
        assert data[0]["timestamp_ms"] == 300

    @pytest.mark.asyncio
    async def test_list_events_nonexistent_session(self, client: AsyncClient):
        """GET /api/events/{session_id} with invalid ID should return 404."""
        response = await client.get("/api/events/nonexistent-session")
        assert response.status_code == 404


class TestEventTypes:
    """Tests for event types endpoint."""

    @pytest.mark.asyncio
    async def test_list_event_types(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id}/types should return unique types."""
        session = Session(id="test-session-5", name="Test", source_type="video_file", status="recording")
        test_db.add(session)

        events = [
            Event(session_id="test-session-5", timestamp_ms=100, event_type="shot"),
            Event(session_id="test-session-5", timestamp_ms=200, event_type="pocket"),
            Event(session_id="test-session-5", timestamp_ms=300, event_type="shot"),
            Event(session_id="test-session-5", timestamp_ms=400, event_type="foul"),
        ]
        for e in events:
            test_db.add(e)
        await test_db.commit()

        response = await client.get("/api/events/test-session-5/types")
        assert response.status_code == 200
        data = response.json()
        assert set(data["event_types"]) == {"shot", "pocket", "foul"}

    @pytest.mark.asyncio
    async def test_list_event_types_empty(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id}/types with no events should return empty list."""
        session = Session(id="test-session-6", name="Test", source_type="video_file", status="pending")
        test_db.add(session)
        await test_db.commit()

        response = await client.get("/api/events/test-session-6/types")
        assert response.status_code == 200
        assert response.json()["event_types"] == []


class TestLatestEvents:
    """Tests for latest events endpoint."""

    @pytest.mark.asyncio
    async def test_get_latest_events(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id}/latest should return most recent events."""
        session = Session(id="test-session-7", name="Test", source_type="video_file", status="recording")
        test_db.add(session)

        # Create 20 events
        for i in range(20):
            test_db.add(Event(
                session_id="test-session-7",
                timestamp_ms=i * 100,
                event_type="shot"
            ))
        await test_db.commit()

        response = await client.get("/api/events/test-session-7/latest?count=5")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
        # Should be in chronological order (oldest to newest of the latest 5)
        assert data[0]["timestamp_ms"] == 1500
        assert data[4]["timestamp_ms"] == 1900

    @pytest.mark.asyncio
    async def test_get_latest_events_default_count(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/events/{session_id}/latest should default to 10 events."""
        session = Session(id="test-session-8", name="Test", source_type="video_file", status="recording")
        test_db.add(session)

        for i in range(15):
            test_db.add(Event(
                session_id="test-session-8",
                timestamp_ms=i * 100,
                event_type="shot"
            ))
        await test_db.commit()

        response = await client.get("/api/events/test-session-8/latest")
        assert response.status_code == 200
        assert len(response.json()) == 10
