"""Unit tests for WebSocket connection manager."""
import pytest
from unittest.mock import AsyncMock, MagicMock
import asyncio

from app.api.websockets.events import ConnectionManager


class TestConnectionManager:
    """Tests for the WebSocket ConnectionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a fresh ConnectionManager for each test."""
        return ConnectionManager()

    @pytest.fixture
    def mock_websocket(self):
        """Create a mock WebSocket."""
        ws = AsyncMock()
        ws.accept = AsyncMock()
        ws.send_text = AsyncMock()
        ws.send_json = AsyncMock()
        return ws

    @pytest.mark.asyncio
    async def test_connect_creates_session_set(self, manager, mock_websocket):
        """Connect should create a set for the session if it doesn't exist."""
        await manager.connect("session-1", mock_websocket)

        assert "session-1" in manager.active_connections
        assert mock_websocket in manager.active_connections["session-1"]
        mock_websocket.accept.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_multiple_clients_same_session(self, manager):
        """Multiple clients can connect to the same session."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        await manager.connect("session-1", ws1)
        await manager.connect("session-1", ws2)
        await manager.connect("session-1", ws3)

        assert len(manager.active_connections["session-1"]) == 3

    @pytest.mark.asyncio
    async def test_connect_different_sessions(self, manager):
        """Clients connecting to different sessions are tracked separately."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("session-1", ws1)
        await manager.connect("session-2", ws2)

        assert "session-1" in manager.active_connections
        assert "session-2" in manager.active_connections
        assert ws1 in manager.active_connections["session-1"]
        assert ws2 in manager.active_connections["session-2"]

    @pytest.mark.asyncio
    async def test_disconnect_removes_client(self, manager, mock_websocket):
        """Disconnect should remove the client from the session."""
        await manager.connect("session-1", mock_websocket)
        await manager.disconnect("session-1", mock_websocket)

        # Session should be removed when no clients remain
        assert "session-1" not in manager.active_connections

    @pytest.mark.asyncio
    async def test_disconnect_keeps_other_clients(self, manager):
        """Disconnect should keep other clients in the session."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("session-1", ws1)
        await manager.connect("session-1", ws2)
        await manager.disconnect("session-1", ws1)

        assert "session-1" in manager.active_connections
        assert ws2 in manager.active_connections["session-1"]
        assert ws1 not in manager.active_connections["session-1"]

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent_session(self, manager, mock_websocket):
        """Disconnect on nonexistent session should not raise error."""
        # Should not raise
        await manager.disconnect("nonexistent", mock_websocket)

    @pytest.mark.asyncio
    async def test_broadcast_sends_to_all_clients(self, manager):
        """Broadcast should send message to all connected clients."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws3 = AsyncMock()

        await manager.connect("session-1", ws1)
        await manager.connect("session-1", ws2)
        await manager.connect("session-1", ws3)

        await manager.broadcast("session-1", {"type": "test", "data": "hello"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_called_once()
        ws3.send_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_broadcast_only_to_target_session(self, manager):
        """Broadcast should only send to clients in the target session."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("session-1", ws1)
        await manager.connect("session-2", ws2)

        await manager.broadcast("session-1", {"type": "test"})

        ws1.send_text.assert_called_once()
        ws2.send_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_broadcast_to_nonexistent_session(self, manager):
        """Broadcast to nonexistent session should not raise error."""
        # Should not raise
        await manager.broadcast("nonexistent", {"type": "test"})

    @pytest.mark.asyncio
    async def test_broadcast_removes_dead_connections(self, manager):
        """Broadcast should remove clients that fail to receive."""
        ws1 = AsyncMock()
        ws2 = AsyncMock()
        ws2.send_text.side_effect = Exception("Connection lost")

        await manager.connect("session-1", ws1)
        await manager.connect("session-1", ws2)

        await manager.broadcast("session-1", {"type": "test"})

        # ws2 should be removed due to error
        assert ws1 in manager.active_connections["session-1"]
        assert ws2 not in manager.active_connections.get("session-1", set())

    @pytest.mark.asyncio
    async def test_get_connection_count(self, manager):
        """get_connection_count should return correct number of clients."""
        assert manager.get_connection_count("session-1") == 0

        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect("session-1", ws1)
        assert manager.get_connection_count("session-1") == 1

        await manager.connect("session-1", ws2)
        assert manager.get_connection_count("session-1") == 2

        await manager.disconnect("session-1", ws1)
        assert manager.get_connection_count("session-1") == 1

    @pytest.mark.asyncio
    async def test_concurrent_connections(self, manager):
        """Manager should handle concurrent connections safely."""
        websockets = [AsyncMock() for _ in range(10)]

        # Connect all concurrently
        await asyncio.gather(*[
            manager.connect("session-1", ws) for ws in websockets
        ])

        assert manager.get_connection_count("session-1") == 10

        # Disconnect half concurrently
        await asyncio.gather(*[
            manager.disconnect("session-1", ws) for ws in websockets[:5]
        ])

        assert manager.get_connection_count("session-1") == 5
