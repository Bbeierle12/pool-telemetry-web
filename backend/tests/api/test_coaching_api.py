"""API integration tests for coaching endpoints."""
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.database import Session, Shot


class TestAnalyzeSession:
    """Tests for session analysis endpoint."""

    @pytest.mark.asyncio
    async def test_analyze_session_no_api_key(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/coaching/{session_id}/analyze without API key returns fallback."""
        session = Session(
            id="coaching-test-1",
            name="Test Session",
            source_type="video_file",
            status="completed",
            total_shots=10,
            total_pocketed=6,
            total_fouls=2
        )
        test_db.add(session)
        await test_db.commit()

        # Patch settings to have no API key
        with patch("app.api.routes.coaching.settings") as mock_settings:
            mock_settings.anthropic_api_key = None

            response = await client.post("/api/coaching/coaching-test-1/analyze")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "unavailable"
            assert "fallback_feedback" in data

    @pytest.mark.asyncio
    async def test_analyze_session_not_found(self, client: AsyncClient):
        """POST /api/coaching/{session_id}/analyze with invalid session returns 404."""
        with patch("app.api.routes.coaching.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"

            response = await client.post("/api/coaching/nonexistent-session/analyze")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_analyze_session_with_mock_ai(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/coaching/{session_id}/analyze with mocked AI."""
        session = Session(
            id="coaching-test-2",
            name="Test Session",
            source_type="video_file",
            status="completed",
            total_shots=10,
            total_pocketed=6,
            total_fouls=2
        )
        test_db.add(session)

        # Add some shots
        for i in range(3):
            test_db.add(Shot(
                session_id="coaching-test-2",
                shot_number=i + 1,
                game_number=1
            ))
        await test_db.commit()

        # Mock the anthropic client
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Great session! You showed good technique.")]

        with patch("app.api.routes.coaching.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"

            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_response
                mock_anthropic.return_value = mock_client

                response = await client.post("/api/coaching/coaching-test-2/analyze")
                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "success"
                assert "analysis" in data
                assert data["shots_analyzed"] == 3


class TestShotFeedback:
    """Tests for shot feedback endpoint."""

    @pytest.mark.asyncio
    async def test_shot_feedback_no_api_key(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/coaching/{session_id}/shots/{shot_number}/feedback without API key."""
        session = Session(
            id="coaching-test-3",
            name="Test Session",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)
        test_db.add(Shot(
            session_id="coaching-test-3",
            shot_number=1,
            game_number=1
        ))
        await test_db.commit()

        with patch("app.api.routes.coaching.settings") as mock_settings:
            mock_settings.anthropic_api_key = None

            response = await client.post("/api/coaching/coaching-test-3/shots/1/feedback")
            assert response.status_code == 200

            data = response.json()
            assert data["status"] == "unavailable"
            assert "fallback_feedback" in data

    @pytest.mark.asyncio
    async def test_shot_feedback_not_found(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/coaching/{session_id}/shots/{shot_number}/feedback with invalid shot."""
        session = Session(
            id="coaching-test-4",
            name="Test Session",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)
        await test_db.commit()

        with patch("app.api.routes.coaching.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"

            response = await client.post("/api/coaching/coaching-test-4/shots/999/feedback")
            assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_shot_feedback_with_mock_ai(self, client: AsyncClient, test_db: AsyncSession):
        """POST /api/coaching/{session_id}/shots/{shot_number}/feedback with mocked AI."""
        session = Session(
            id="coaching-test-5",
            name="Test Session",
            source_type="video_file",
            status="completed"
        )
        test_db.add(session)
        test_db.add(Shot(
            session_id="coaching-test-5",
            shot_number=1,
            game_number=1
        ))
        await test_db.commit()

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text="Nice follow through on that shot!")]

        with patch("app.api.routes.coaching.settings") as mock_settings:
            mock_settings.anthropic_api_key = "test-key"

            with patch("anthropic.Anthropic") as mock_anthropic:
                mock_client = MagicMock()
                mock_client.messages.create.return_value = mock_response
                mock_anthropic.return_value = mock_client

                response = await client.post("/api/coaching/coaching-test-5/shots/1/feedback")
                assert response.status_code == 200

                data = response.json()
                assert data["status"] == "success"
                assert "feedback" in data
                assert data["shot_number"] == 1


class TestSuggestDrills:
    """Tests for drill suggestion endpoint."""

    @pytest.mark.asyncio
    async def test_suggest_drills_low_accuracy(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/coaching/{session_id}/drills with low accuracy."""
        session = Session(
            id="coaching-test-6",
            name="Test Session",
            source_type="video_file",
            status="completed",
            total_shots=20,
            total_pocketed=4,  # 20% accuracy
            total_fouls=1
        )
        test_db.add(session)
        await test_db.commit()

        response = await client.get("/api/coaching/coaching-test-6/drills")
        assert response.status_code == 200

        data = response.json()
        assert data["accuracy_rate"] == 0.2
        assert len(data["suggested_drills"]) > 0
        # Should suggest basic drills for low accuracy
        drill_names = [d["name"] for d in data["suggested_drills"]]
        assert "Straight-In Shots" in drill_names

    @pytest.mark.asyncio
    async def test_suggest_drills_high_foul_rate(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/coaching/{session_id}/drills with high foul rate."""
        session = Session(
            id="coaching-test-7",
            name="Test Session",
            source_type="video_file",
            status="completed",
            total_shots=10,
            total_pocketed=5,
            total_fouls=4  # 40% foul rate
        )
        test_db.add(session)
        await test_db.commit()

        response = await client.get("/api/coaching/coaching-test-7/drills")
        assert response.status_code == 200

        data = response.json()
        assert data["foul_rate"] == 0.4
        drill_names = [d["name"] for d in data["suggested_drills"]]
        assert "Cue Ball Control" in drill_names

    @pytest.mark.asyncio
    async def test_suggest_drills_high_accuracy(self, client: AsyncClient, test_db: AsyncSession):
        """GET /api/coaching/{session_id}/drills with high accuracy."""
        session = Session(
            id="coaching-test-8",
            name="Test Session",
            source_type="video_file",
            status="completed",
            total_shots=20,
            total_pocketed=14,  # 70% accuracy
            total_fouls=1
        )
        test_db.add(session)
        await test_db.commit()

        response = await client.get("/api/coaching/coaching-test-8/drills")
        assert response.status_code == 200

        data = response.json()
        assert data["accuracy_rate"] == 0.7
        drill_names = [d["name"] for d in data["suggested_drills"]]
        assert "Position Play" in drill_names

    @pytest.mark.asyncio
    async def test_suggest_drills_not_found(self, client: AsyncClient):
        """GET /api/coaching/{session_id}/drills with invalid session returns 404."""
        response = await client.get("/api/coaching/nonexistent-session/drills")
        assert response.status_code == 404
