"""Log API tests.

Tests cover reading backend log files, filtering by level and keyword,
and retrieving log file metadata.
"""

import pytest

from tests.factories import assert_status


@pytest.mark.asyncio
@pytest.mark.api
class TestLogAPI:
    """Log API integration tests."""

    async def test_get_logs(self, client):
        """TC-API-LOG-001: Get backend logs without filters.

        Verifies:
        - Response status is 200
        - Response contains 'data' with log entries
        - Response includes 'total', 'returned', 'file', and 'entries' fields
        - 'entries' is a list
        """
        response = await client.get("/api/logs")
        data = await assert_status(response, 200)

        assert "data" in data
        log_data = data["data"]
        assert "total" in log_data
        assert "returned" in log_data
        assert "file" in log_data
        assert "entries" in log_data
        assert isinstance(log_data["entries"], list)
        assert log_data["returned"] >= 0
        assert log_data["total"] >= 0

        # If there are entries, verify their structure
        if log_data["entries"]:
            entry = log_data["entries"][0]
            assert "timestamp" in entry
            assert "level" in entry
            assert "logger" in entry
            assert "message" in entry

    async def test_get_logs_with_level_filter(self, client):
        """TC-API-LOG-002: Get logs filtered by level.

        Verifies:
        - Filtering by 'ERROR' returns only ERROR-level entries
        - All returned entries have the requested level
        """
        response = await client.get("/api/logs?level=ERROR")
        data = await assert_status(response, 200)

        log_data = data["data"]
        for entry in log_data["entries"]:
            assert entry["level"] == "ERROR"

    async def test_get_logs_with_keyword(self, client):
        """TC-API-LOG-003: Get logs filtered by keyword.

        Verifies:
        - Filtering by keyword returns only matching entries
        - All returned entries contain the keyword in their message
        """
        # Use a keyword that should match the startup log message
        response = await client.get("/api/logs?keyword=初始化")
        data = await assert_status(response, 200)

        log_data = data["data"]
        for entry in log_data["entries"]:
            assert "初始化" in entry["message"].lower() or "初始化" in entry["message"]

    async def test_log_info(self, client):
        """TC-API-LOG-004: Get log file metadata.

        Verifies:
        - Response status is 200
        - Response contains file path, existence flag, and size
        """
        response = await client.get("/api/logs/info")
        data = await assert_status(response, 200)

        assert "data" in data
        info = data["data"]
        assert "file" in info
        assert "exists" in info
        assert "size_bytes" in info
        assert isinstance(info["exists"], bool)
        assert isinstance(info["size_bytes"], int)
