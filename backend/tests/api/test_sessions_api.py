"""API integration tests for session management endpoints."""
import pytest
from httpx import AsyncClient


class TestSessionCreation:
    """Tests for session creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_session_success(self, client: AsyncClient):
        """POST /api/sessions should create a new session."""
        response = await client.post("/api/sessions", json={
            "source_type": "video_file",
            "name": "Test Session"
        })
        assert response.status_code == 201

        data = response.json()
        assert data["name"] == "Test Session"
        assert data["source_type"] == "video_file"
        assert data["status"] == "pending"
        assert "id" in data
        assert "created_at" in data

    @pytest.mark.asyncio
    async def test_create_session_auto_name(self, client: AsyncClient):
        """Session without name should get auto-generated name."""
        response = await client.post("/api/sessions", json={
            "source_type": "gopro_wifi"
        })
        assert response.status_code == 201
        assert "Session" in response.json()["name"]

    @pytest.mark.asyncio
    async def test_create_session_missing_source_type(self, client: AsyncClient):
        """Creating session without source_type should fail."""
        response = await client.post("/api/sessions", json={
            "name": "Test"
        })
        assert response.status_code == 422


class TestSessionListing:
    """Tests for session listing endpoint."""

    @pytest.mark.asyncio
    async def test_list_sessions_empty(self, client: AsyncClient):
        """GET /api/sessions should return empty list initially."""
        response = await client.get("/api/sessions")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_list_sessions_after_creation(self, client: AsyncClient):
        """GET /api/sessions should return created sessions."""
        # Create sessions
        await client.post("/api/sessions", json={"source_type": "video_file", "name": "Session 1"})
        await client.post("/api/sessions", json={"source_type": "video_file", "name": "Session 2"})

        response = await client.get("/api/sessions")
        assert response.status_code == 200
        sessions = response.json()
        assert len(sessions) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_pagination(self, client: AsyncClient):
        """GET /api/sessions should support pagination."""
        # Create 5 sessions
        for i in range(5):
            await client.post("/api/sessions", json={"source_type": "video_file", "name": f"Session {i}"})

        # Get first 2
        response = await client.get("/api/sessions?limit=2")
        assert len(response.json()) == 2

        # Get next 2
        response = await client.get("/api/sessions?skip=2&limit=2")
        assert len(response.json()) == 2

    @pytest.mark.asyncio
    async def test_list_sessions_filter_by_status(self, client: AsyncClient):
        """GET /api/sessions should filter by status."""
        # Create session and start it
        create_response = await client.post("/api/sessions", json={"source_type": "video_file"})
        session_id = create_response.json()["id"]
        await client.post(f"/api/sessions/{session_id}/start")

        # Create another pending session
        await client.post("/api/sessions", json={"source_type": "video_file"})

        # Filter by status
        response = await client.get("/api/sessions?status=recording")
        sessions = response.json()
        assert len(sessions) == 1
        assert sessions[0]["status"] == "recording"


class TestSessionRetrieval:
    """Tests for single session retrieval."""

    @pytest.mark.asyncio
    async def test_get_session_success(self, client: AsyncClient):
        """GET /api/sessions/{id} should return session details."""
        # Create session
        create_response = await client.post("/api/sessions", json={
            "source_type": "video_file",
            "name": "My Session"
        })
        session_id = create_response.json()["id"]

        # Get session
        response = await client.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["id"] == session_id
        assert response.json()["name"] == "My Session"

    @pytest.mark.asyncio
    async def test_get_session_not_found(self, client: AsyncClient):
        """GET /api/sessions/{id} with invalid ID should return 404."""
        response = await client.get("/api/sessions/nonexistent-id")
        assert response.status_code == 404
        assert "Session not found" in response.json()["detail"]


class TestSessionLifecycle:
    """Tests for session start/stop lifecycle."""

    @pytest.mark.asyncio
    async def test_start_session(self, client: AsyncClient):
        """POST /api/sessions/{id}/start should start recording."""
        # Create session
        create_response = await client.post("/api/sessions", json={"source_type": "video_file"})
        session_id = create_response.json()["id"]
        assert create_response.json()["status"] == "pending"

        # Start session
        response = await client.post(f"/api/sessions/{session_id}/start")
        assert response.status_code == 200
        assert response.json()["status"] == "recording"
        assert response.json()["started_at"] is not None

    @pytest.mark.asyncio
    async def test_stop_session(self, client: AsyncClient):
        """POST /api/sessions/{id}/stop should complete session."""
        # Create and start session
        create_response = await client.post("/api/sessions", json={"source_type": "video_file"})
        session_id = create_response.json()["id"]
        await client.post(f"/api/sessions/{session_id}/start")

        # Stop session
        response = await client.post(f"/api/sessions/{session_id}/stop")
        assert response.status_code == 200
        assert response.json()["status"] == "completed"
        assert response.json()["ended_at"] is not None

    @pytest.mark.asyncio
    async def test_start_nonexistent_session(self, client: AsyncClient):
        """Starting non-existent session should return 404."""
        response = await client.post("/api/sessions/nonexistent-id/start")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_stop_nonexistent_session(self, client: AsyncClient):
        """Stopping non-existent session should return 404."""
        response = await client.post("/api/sessions/nonexistent-id/stop")
        assert response.status_code == 404


class TestSessionUpdate:
    """Tests for session update endpoint."""

    @pytest.mark.asyncio
    async def test_update_session_name(self, client: AsyncClient):
        """PATCH /api/sessions/{id} should update session fields."""
        # Create session
        create_response = await client.post("/api/sessions", json={
            "source_type": "video_file",
            "name": "Original Name"
        })
        session_id = create_response.json()["id"]

        # Update name
        response = await client.patch(f"/api/sessions/{session_id}", json={
            "name": "Updated Name"
        })
        assert response.status_code == 200
        assert response.json()["name"] == "Updated Name"

    @pytest.mark.asyncio
    async def test_update_session_status(self, client: AsyncClient):
        """PATCH should handle status transitions."""
        # Create session
        create_response = await client.post("/api/sessions", json={"source_type": "video_file"})
        session_id = create_response.json()["id"]

        # Update to recording status
        response = await client.patch(f"/api/sessions/{session_id}", json={
            "status": "recording"
        })
        assert response.status_code == 200
        assert response.json()["status"] == "recording"
        assert response.json()["started_at"] is not None

    @pytest.mark.asyncio
    async def test_update_nonexistent_session(self, client: AsyncClient):
        """Updating non-existent session should return 404."""
        response = await client.patch("/api/sessions/nonexistent-id", json={
            "name": "Test"
        })
        assert response.status_code == 404


class TestSessionDeletion:
    """Tests for session deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_session_success(self, client: AsyncClient):
        """DELETE /api/sessions/{id} should delete session."""
        # Create session
        create_response = await client.post("/api/sessions", json={"source_type": "video_file"})
        session_id = create_response.json()["id"]

        # Delete session
        response = await client.delete(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["status"] == "deleted"

        # Verify deletion
        get_response = await client.get(f"/api/sessions/{session_id}")
        assert get_response.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, client: AsyncClient):
        """Deleting non-existent session should return 404."""
        response = await client.delete("/api/sessions/nonexistent-id")
        assert response.status_code == 404


class TestSessionStats:
    """Tests for session statistics endpoint."""

    @pytest.mark.asyncio
    async def test_get_session_stats(self, client: AsyncClient):
        """GET /api/sessions/{id}/stats should return statistics."""
        # Create session
        create_response = await client.post("/api/sessions", json={"source_type": "video_file"})
        session_id = create_response.json()["id"]

        # Get stats
        response = await client.get(f"/api/sessions/{session_id}/stats")
        assert response.status_code == 200

        stats = response.json()
        assert stats["session_id"] == session_id
        assert "total_shots" in stats
        assert "total_pocketed" in stats
        assert "total_fouls" in stats
        assert "total_events" in stats

    @pytest.mark.asyncio
    async def test_get_stats_nonexistent_session(self, client: AsyncClient):
        """Getting stats for non-existent session should return 404."""
        response = await client.get("/api/sessions/nonexistent-id/stats")
        assert response.status_code == 404
