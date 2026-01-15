"""API integration tests for export endpoints."""
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Session, Shot, Event


class TestExportSession:
    """Tests for session export endpoints."""

    @pytest.mark.asyncio
    async def test_export_full_json(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/export/{session_id} with full_json format."""
        # Create session with data
        session = Session(
            id="export-test-1",
            name="Export Test",
            source_type="video_file",
            status="completed",
            total_shots=5,
            total_pocketed=3,
            total_fouls=1
        )
        test_db.add(session)
        await test_db.commit()

        response = await client.post("/api/export/export-test-1", json={
            "format": "full_json"
        })
        assert response.status_code == 200

        data = response.json()
        assert "download_url" in data
        assert "filename" in data
        assert data["format"] == "full_json"
        assert data["file_size_bytes"] > 0
        assert "full.json" in data["filename"]

    @pytest.mark.asyncio
    async def test_export_claude_json(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/export/{session_id} with claude_json format."""
        session = Session(
            id="export-test-2",
            name="Export Test 2",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)
        await test_db.commit()

        response = await client.post("/api/export/export-test-2", json={
            "format": "claude_json"
        })
        assert response.status_code == 200
        assert "claude.json" in response.json()["filename"]

    @pytest.mark.asyncio
    async def test_export_shots_csv(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/export/{session_id} with shots_csv format."""
        session = Session(
            id="export-test-3",
            name="Export Test 3",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)

        # Add some shots
        for i in range(3):
            test_db.add(Shot(
                session_id="export-test-3",
                shot_number=i + 1,
                game_number=1
            ))
        await test_db.commit()

        response = await client.post("/api/export/export-test-3", json={
            "format": "shots_csv"
        })
        assert response.status_code == 200
        assert "shots.csv" in response.json()["filename"]

    @pytest.mark.asyncio
    async def test_export_events_jsonl(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/export/{session_id} with events_jsonl format."""
        session = Session(
            id="export-test-4",
            name="Export Test 4",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)

        # Add some events
        for i in range(5):
            test_db.add(Event(
                session_id="export-test-4",
                timestamp_ms=i * 1000,
                event_type="shot"
            ))
        await test_db.commit()

        response = await client.post("/api/export/export-test-4", json={
            "format": "events_jsonl"
        })
        assert response.status_code == 200
        assert "events.jsonl" in response.json()["filename"]

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/export/{session_id} with invalid format should fail."""
        session = Session(
            id="export-test-5",
            name="Export Test 5",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)
        await test_db.commit()

        response = await client.post("/api/export/export-test-5", json={
            "format": "invalid_format"
        })
        assert response.status_code == 400
        assert "Unknown format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_export_nonexistent_session(self, client: AsyncClient):
        """POST /api/export/{session_id} with invalid session should return 404."""
        response = await client.post("/api/export/nonexistent-session", json={
            "format": "full_json"
        })
        assert response.status_code == 404


class TestDownloadExport:
    """Tests for export download endpoint."""

    @pytest.mark.asyncio
    async def test_download_export_not_found(self, client: AsyncClient):
        """GET /api/export/download/{filename} with invalid filename should return 404."""
        response = await client.get("/api/export/download/nonexistent_file.json")
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_download_after_export(self, client: AsyncClient, test_db: AsyncSession):
        """Should be able to download after export."""
        # Create and export session
        session = Session(
            id="export-test-6",
            name="Export Test 6",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)
        await test_db.commit()

        export_response = await client.post("/api/export/export-test-6", json={
            "format": "full_json"
        })
        assert export_response.status_code == 200

        # Download the export
        download_url = export_response.json()["download_url"]
        download_response = await client.get(download_url)
        assert download_response.status_code == 200
        assert download_response.headers["content-type"] == "application/json"
