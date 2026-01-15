"""API tests for health check endpoints."""
import pytest
from httpx import AsyncClient


class TestHealthEndpoints:
    """Tests for health check endpoints."""

    @pytest.mark.asyncio
    async def test_root_endpoint(self, client: AsyncClient):
        """GET / should return OK status."""
        response = await client.get("/")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "ok"
        assert data["version"] == "2.0.0"
        assert "app" in data

    @pytest.mark.asyncio
    async def test_health_endpoint(self, client: AsyncClient):
        """GET /api/health should return detailed health status."""
        response = await client.get("/api/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert "gemini_configured" in data
        assert "anthropic_configured" in data
        assert isinstance(data["gemini_configured"], bool)
        assert isinstance(data["anthropic_configured"], bool)
