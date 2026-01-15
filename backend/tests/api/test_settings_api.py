"""API integration tests for settings endpoints."""
import pytest
from httpx import AsyncClient


class TestGetSettings:
    """Tests for retrieving settings."""

    @pytest.mark.asyncio
    async def test_get_all_settings(self, client: AsyncClient):
        """GET /api/settings should return all settings with defaults."""
        response = await client.get("/api/settings")
        assert response.status_code == 200

        data = response.json()
        assert "api_keys" in data
        assert "gopro" in data
        assert "video" in data
        assert "analysis" in data
        assert "storage" in data
        assert "cost" in data
        assert "display" in data
        assert "notifications" in data

    @pytest.mark.asyncio
    async def test_get_settings_default_values(self, client: AsyncClient):
        """GET /api/settings should return sensible defaults."""
        response = await client.get("/api/settings")
        data = response.json()

        # Check some default values
        assert data["video"]["default_resolution"] == "1080p"
        assert data["video"]["default_framerate"] == 30
        assert data["cost"]["warning_threshold"] == 5.0
        assert data["cost"]["stop_threshold"] == 10.0
        assert data["display"]["theme"] == "dark"


class TestUpdateSettings:
    """Tests for updating settings."""

    @pytest.mark.asyncio
    async def test_update_all_settings(self, client: AsyncClient):
        """PUT /api/settings should update all settings."""
        new_settings = {
            "api_keys": {"gemini_key": None, "anthropic_key": None},
            "gopro": {
                "connection_mode": "usb",
                "wifi_ip": "10.5.5.9",
                "wifi_port": 8080,
                "protocol": "udp",
                "resolution": "4k",
                "framerate": 60,
                "stabilization": False
            },
            "video": {
                "default_resolution": "4k",
                "default_framerate": 60,
                "hls_segment_duration": 4,
                "save_original": True,
                "auto_process": False
            },
            "analysis": {
                "ai_provider": "anthropic",
                "gemini_model": "gemini-2.0-flash-exp",
                "anthropic_model": "claude-3-5-sonnet-20241022",
                "frame_sample_rate_ms": 66,
                "enable_ball_tracking": True,
                "enable_shot_detection": True,
                "enable_foul_detection": False,
                "confidence_threshold": 0.8,
                "system_prompt": "Custom prompt"
            },
            "storage": {
                "data_directory": "./data",
                "save_key_frames": False,
                "save_raw_events": True,
                "frame_quality": 90,
                "max_storage_gb": 100,
                "auto_cleanup_days": 60
            },
            "cost": {
                "enabled": True,
                "warning_threshold": 10.0,
                "stop_threshold": 20.0,
                "track_per_session": True
            },
            "display": {
                "theme": "light",
                "show_ball_labels": False,
                "show_trajectory": True,
                "show_confidence": False,
                "event_log_max_lines": 1000,
                "auto_scroll_events": False,
                "compact_mode": True
            },
            "notifications": {
                "enable_sounds": True,
                "enable_desktop": False,
                "notify_on_shot": True,
                "notify_on_foul": True,
                "notify_on_pocket": True,
                "notify_on_cost_warning": True
            }
        }

        response = await client.put("/api/settings", json=new_settings)
        assert response.status_code == 200

        data = response.json()
        assert data["gopro"]["resolution"] == "4k"
        assert data["display"]["theme"] == "light"
        assert data["cost"]["warning_threshold"] == 10.0

    @pytest.mark.asyncio
    async def test_update_api_keys(self, client: AsyncClient):
        """PATCH /api/settings/api-keys should update only API keys."""
        response = await client.patch("/api/settings/api-keys", json={
            "gemini_key": "test-gemini-key",
            "anthropic_key": "test-anthropic-key"
        })
        assert response.status_code == 200

        data = response.json()
        assert data["gemini_key"] == "test-gemini-key"
        assert data["anthropic_key"] == "test-anthropic-key"

    @pytest.mark.asyncio
    async def test_update_gopro_settings(self, client: AsyncClient):
        """PATCH /api/settings/gopro should update GoPro settings."""
        response = await client.patch("/api/settings/gopro", json={
            "connection_mode": "usb",
            "wifi_ip": "192.168.1.100",
            "wifi_port": 9000,
            "protocol": "tcp",
            "resolution": "4k",
            "framerate": 120,
            "stabilization": False
        })
        assert response.status_code == 200

        data = response.json()
        assert data["connection_mode"] == "usb"
        assert data["resolution"] == "4k"
        assert data["framerate"] == 120

    @pytest.mark.asyncio
    async def test_update_analysis_settings(self, client: AsyncClient):
        """PATCH /api/settings/analysis should update analysis settings."""
        response = await client.patch("/api/settings/analysis", json={
            "ai_provider": "none",
            "gemini_model": "gemini-2.0-flash-exp",
            "anthropic_model": "claude-3-5-sonnet-20241022",
            "frame_sample_rate_ms": 100,
            "enable_ball_tracking": False,
            "enable_shot_detection": True,
            "enable_foul_detection": False,
            "confidence_threshold": 0.9,
            "system_prompt": "New prompt"
        })
        assert response.status_code == 200

        data = response.json()
        assert data["ai_provider"] == "none"
        assert data["confidence_threshold"] == 0.9

    @pytest.mark.asyncio
    async def test_update_display_settings(self, client: AsyncClient):
        """PATCH /api/settings/display should update display settings."""
        response = await client.patch("/api/settings/display", json={
            "theme": "light",
            "show_ball_labels": False,
            "show_trajectory": False,
            "show_confidence": True,
            "event_log_max_lines": 200,
            "auto_scroll_events": False,
            "compact_mode": True
        })
        assert response.status_code == 200

        data = response.json()
        assert data["theme"] == "light"
        assert data["compact_mode"] is True


class TestStorageInfo:
    """Tests for storage information endpoints."""

    @pytest.mark.asyncio
    async def test_get_storage_info(self, client: AsyncClient):
        """GET /api/settings/storage/info should return storage metrics."""
        response = await client.get("/api/settings/storage/info")
        assert response.status_code == 200

        data = response.json()
        assert "total_size_mb" in data
        assert "sessions_count" in data
        assert "videos_count" in data
        assert "exports_count" in data
        assert "hls_size_mb" in data
        assert "uploads_size_mb" in data
        assert isinstance(data["total_size_mb"], (int, float))


class TestStorageCleanup:
    """Tests for storage cleanup endpoints."""

    @pytest.mark.asyncio
    async def test_cleanup_storage(self, client: AsyncClient):
        """POST /api/settings/storage/cleanup should return cleanup results."""
        response = await client.post("/api/settings/storage/cleanup?older_than_days=30")
        assert response.status_code == 200

        data = response.json()
        assert "deleted_count" in data
        assert "freed_mb" in data

    @pytest.mark.asyncio
    async def test_clear_cache(self, client: AsyncClient):
        """POST /api/settings/storage/clear-cache should clear cache."""
        response = await client.post("/api/settings/storage/clear-cache")
        assert response.status_code == 200
        assert "cleared" in response.json()["message"].lower()


class TestSystemInfo:
    """Tests for system information endpoint."""

    @pytest.mark.asyncio
    async def test_get_system_info(self, client: AsyncClient):
        """GET /api/settings/system/info should return system information."""
        response = await client.get("/api/settings/system/info")
        assert response.status_code == 200

        data = response.json()
        assert data["app_version"] == "2.0.0"
        assert "python_version" in data
        assert "platform" in data
        assert "opencv_version" in data
        assert "gemini_configured" in data
        assert "anthropic_configured" in data


class TestResetSettings:
    """Tests for settings reset."""

    @pytest.mark.asyncio
    async def test_reset_settings(self, client: AsyncClient):
        """POST /api/settings/reset should reset to defaults."""
        # First modify some settings
        await client.patch("/api/settings/display", json={
            "theme": "light",
            "show_ball_labels": False,
            "show_trajectory": False,
            "show_confidence": True,
            "event_log_max_lines": 200,
            "auto_scroll_events": False,
            "compact_mode": True
        })

        # Reset
        response = await client.post("/api/settings/reset")
        assert response.status_code == 200
        assert "reset" in response.json()["message"].lower()

        # Verify defaults restored
        get_response = await client.get("/api/settings")
        data = get_response.json()
        assert data["display"]["theme"] == "dark"
        assert data["display"]["show_ball_labels"] is True
