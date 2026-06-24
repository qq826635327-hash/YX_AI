"""WebSocket 路由：任务状态、剧本解析进度推送。"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

ws_router = APIRouter()


# ============================================================
# 连接管理器
# ============================================================

class ConnectionManager:
    """WebSocket 连接管理器（按频道分组）。"""

    def __init__(self):
        # channel -> set of WebSocket
        self._channels: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, channel: str = "default") -> None:
        await websocket.accept()
        if channel not in self._channels:
            self._channels[channel] = set()
        self._channels[channel].add(websocket)

    def disconnect(self, websocket: WebSocket, channel: str = "default") -> None:
        if channel in self._channels:
            self._channels[channel].discard(websocket)
            if not self._channels[channel]:
                del self._channels[channel]

    async def broadcast(self, channel: str, message: dict) -> None:
        """向某个频道所有连接广播消息（并行发送，避免慢连接拖慢整体）。"""
        if channel not in self._channels:
            return
        text = json.dumps(message, ensure_ascii=False, default=str)
        # 复制快照遍历，避免 disconnect() 并发修改 set 导致 RuntimeError
        peers = list(self._channels[channel])
        if not peers:
            return

        # 并行发送，单个连接异常不阻塞其他连接
        async def _safe_send(ws: WebSocket) -> WebSocket | None:
            try:
                await ws.send_text(text)
                return None  # 发送成功
            except Exception:
                return ws  # 返回死连接

        results = await asyncio.gather(*[_safe_send(ws) for ws in peers])
        dead = [ws for ws in results if ws is not None]
        for ws in dead:
            self._channels[channel].discard(ws)

    async def send_personal(self, websocket: WebSocket, message: dict) -> None:
        text = json.dumps(message, ensure_ascii=False, default=str)
        await websocket.send_text(text)


# 全局单例
manager = ConnectionManager()


def make_message(msg_type: str, data: dict) -> dict:
    """构造标准 WebSocket 消息。"""
    from datetime import datetime, timezone
    return {
        "type": msg_type,
        "data": data,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# ============================================================
# 路由
# ============================================================

async def _ws_channel_handler(websocket: WebSocket, channel: str, extra_commands: dict | None = None) -> None:
    """通用 WebSocket 频道处理逻辑。

    Args:
        channel: 频道名
        extra_commands: 额外的客户端命令处理，如 {"clear": lambda ws: ...}
    """
    await manager.connect(websocket, channel)
    try:
        await manager.send_personal(
            websocket,
            make_message("connected", {"channel": channel}),
        )
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=60.0)
                if data == "ping":
                    await manager.send_personal(websocket, make_message("pong", {}))
                elif extra_commands and data in extra_commands:
                    await extra_commands[data](websocket)
            except asyncio.TimeoutError:
                await manager.send_personal(websocket, make_message("heartbeat", {}))
    except WebSocketDisconnect:
        manager.disconnect(websocket, channel)
    except Exception as e:
        logger.warning(f"WS 频道 {channel} 异常: {e}")
        manager.disconnect(websocket, channel)


@ws_router.websocket("/ws/tasks")
async def ws_tasks(websocket: WebSocket):
    """任务状态推送频道。"""
    await _ws_channel_handler(websocket, "tasks")


@ws_router.websocket("/ws/script")
async def ws_script(websocket: WebSocket):
    """剧本解析进度推送频道。"""
    await _ws_channel_handler(websocket, "script")


@ws_router.websocket("/ws/logs")
async def ws_logs(websocket: WebSocket):
    """实时日志推送频道（仅 ERROR/WARNING）。"""
    async def handle_clear(ws: WebSocket):
        await manager.send_personal(ws, make_message("log.cleared", {}))

    await _ws_channel_handler(websocket, "logs", extra_commands={"clear": handle_clear})


@ws_router.websocket("/ws/perf")
async def ws_perf(websocket: WebSocket):
    """性能告警实时推送频道。"""
    await _ws_channel_handler(websocket, "perf")


# ============================================================
# 对外推送接口（供业务层调用）
# ============================================================

async def push_task_created(task_id: str, project_id: str, **extra) -> None:
    await manager.broadcast(
        "tasks",
        make_message("task.created", {"task_id": task_id, "project_id": project_id, **extra}),
    )


async def push_task_progress(task_id: str, progress: int, **extra) -> None:
    await manager.broadcast(
        "tasks",
        make_message("task.progress", {"task_id": task_id, "progress": progress, **extra}),
    )


async def push_task_completed(task_id: str, target_type: str = "", **extra) -> None:
    await manager.broadcast("tasks", make_message("task.completed", {"task_id": task_id, "target_type": target_type, **extra}))


async def push_task_failed(task_id: str, error: str, target_type: str = "", **extra) -> None:
    await manager.broadcast(
        "tasks",
        make_message("task.failed", {"task_id": task_id, "error": error, "target_type": target_type, **extra}),
    )


async def push_script_progress(project_id: str, stage: str, **extra) -> None:
    """推送解析阶段进度（含已完成步骤列表，供前端重挂载时恢复状态）。"""
    await manager.broadcast(
        "script",
        make_message("script.parsing", {"project_id": project_id, "stage": stage, **extra}),
    )


async def push_script_stream(project_id: str, stage: str, tokens: str) -> None:
    """推送 LLM 流式输出 token（批量，约每 100ms 一次）。"""
    await manager.broadcast(
        "script",
        make_message("script.stream", {"project_id": project_id, "stage": stage, "tokens": tokens}),
    )


async def push_script_stage_done(project_id: str, stage: str, summary: str = "", completed_stages: list | None = None, **extra) -> None:
    """推送某个解析阶段完成。"""
    data = {
        "project_id": project_id,
        "stage": stage,
        "summary": summary,
        **extra,
    }
    if completed_stages is not None:
        data["completed_stages"] = completed_stages
    await manager.broadcast(
        "script",
        make_message("script.stage_done", data),
    )


async def push_script_completed(project_id: str, **extra) -> None:
    await manager.broadcast("script", make_message("script.completed", {"project_id": project_id, **extra}))


async def push_script_failed(project_id: str, error: str, **extra) -> None:
    await manager.broadcast(
        "script",
        make_message("script.failed", {"project_id": project_id, "error": error, **extra}),
    )
