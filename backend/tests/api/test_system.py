"""System API tests.

Tests cover health check, system config, queue status, manual backup,
and task list with status filter.
"""

import pytest


@pytest.mark.asyncio
@pytest.mark.api
class TestSystemAPIs:
    """System API integration tests."""

    async def test_health_check(self, client):
        """TC-API-SYS-001: 健康检查端点返回正确状态。"""
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "app" in data
        assert "version" in data
        assert "database" in data

    async def test_system_config(self, client):
        """TC-API-SYS-002: 系统配置端点返回脱敏配置。"""
        resp = await client.get("/api/config/system")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "app" in data
        assert "comfyui" in data
        assert "llm" in data
        assert "storage" in data

    async def test_queue_status(self, client):
        """TC-API-SYS-003: 任务队列状态端点返回正确结构。"""
        resp = await client.get("/api/tasks/queue/status")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "db" in data
        assert "runtime" in data
        assert "active_tasks" in data["runtime"]
        assert "semaphore_available" in data["runtime"]
        assert "semaphore_max" in data["runtime"]
        assert data["runtime"]["semaphore_max"] == 4

    async def test_manual_backup(self, client):
        """TC-API-SYS-004: 手动备份端点创建备份文件。"""
        resp = await client.post("/api/config/backup")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "backup_file" in data
        assert "wal_checkpoint" in data
        # backup_file 应该是一个文件路径字符串或 null
        if data["backup_file"]:
            assert "app_backup_" in data["backup_file"]
            assert data["backup_file"].endswith(".sqlite")

    async def test_task_list_with_status_filter(self, client):
        """TC-API-SYS-005: 任务列表支持状态过滤。"""
        # 查询 succeeded 状态的任务
        resp = await client.get("/api/tasks", params={"status": "succeeded"})
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "items" in data
        assert "total" in data
        # 所有返回的任务应该是 succeeded 状态
        for task in data["items"]:
            assert task["status"] == "succeeded"
