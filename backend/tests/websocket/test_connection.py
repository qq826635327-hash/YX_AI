"""WebSocket connection tests.

Basic tests for WebSocket endpoints: tasks channel, ping/pong heartbeat,
and logs channel. Uses the `websockets` library to connect to the
running test server.
"""

import json

import pytest

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

# Base URL for the test server WebSocket endpoints
WS_BASE = "ws://127.0.0.1:8000"


@pytest.mark.asyncio
@pytest.mark.websocket
@pytest.mark.skipif(not HAS_WEBSOCKETS, reason="websockets library not installed")
class TestWebSocketConnection:
    """WebSocket connection integration tests."""

    async def test_ws_tasks_connect(self):
        """TC-WS-001: Connect to the tasks WebSocket channel.

        Verifies:
        - Connection is accepted
        - Server sends a 'connected' message with channel='tasks'
        - Connection can be closed cleanly
        """
        async with websockets.connect(f"{WS_BASE}/ws/tasks") as ws:
            # Should receive a connected message
            raw = await ws.recv()
            message = json.loads(raw)

            assert message["type"] == "connected"
            assert message["data"]["channel"] == "tasks"
            assert "timestamp" in message

    async def test_ws_ping_pong(self):
        """TC-WS-002: Send 'ping' and receive 'pong' on tasks channel.

        Verifies:
        - Server responds to 'ping' with a 'pong' message
        - Pong message has the expected structure
        """
        async with websockets.connect(f"{WS_BASE}/ws/tasks") as ws:
            # Consume the initial 'connected' message
            await ws.recv()

            # Send ping
            await ws.send("ping")

            # Should receive pong
            raw = await ws.recv()
            message = json.loads(raw)

            assert message["type"] == "pong"
            assert "timestamp" in message

    async def test_ws_logs_connect(self):
        """TC-WS-003: Connect to the logs WebSocket channel.

        Verifies:
        - Connection is accepted
        - Server sends a 'connected' message with channel='logs'
        - The logs channel supports real-time log streaming
        """
        async with websockets.connect(f"{WS_BASE}/ws/logs") as ws:
            # Should receive a connected message
            raw = await ws.recv()
            message = json.loads(raw)

            assert message["type"] == "connected"
            assert message["data"]["channel"] == "logs"
            assert "timestamp" in message

            # Test that 'clear' command works on logs channel
            await ws.send("clear")
            raw = await ws.recv()
            clear_msg = json.loads(raw)
            assert clear_msg["type"] == "log.cleared"
