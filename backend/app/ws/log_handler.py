"""WebSocket 日志广播 Handler。

把 ERROR / WARNING 级别日志通过 WebSocket 推送到所有连接的客户端，
方便前端开发者实时看到后端错误。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional

# 避免循环导入
_ws_manager: Optional[object] = None


def set_ws_manager(manager) -> None:
    """注入 ConnectionManager 单例（在 app 启动时调用）。"""
    global _ws_manager
    _ws_manager = manager


class WsLogHandler(logging.Handler):
    """通过 WebSocket 广播日志的 Handler。

    设计要点：
    - 仅广播 ERROR / WARNING 级别（不刷屏）
    - 异步非阻塞：使用 run_coroutine_threadsafe 把广播任务投到主事件循环
    - 消息格式与现有 WS 消息一致：{ type, data, timestamp }
    """

    # 哪些级别会广播
    BROADCAST_LEVELS = {logging.ERROR, logging.WARNING}

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        # 主事件循环引用（在 FastAPI 启动后注入）
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """注入主事件循环。"""
        self._loop = loop

    def emit(self, record: logging.LogRecord) -> None:
        """把 LogRecord 转换为 WS 消息并广播。"""
        if record.levelno not in self.BROADCAST_LEVELS:
            return
        if _ws_manager is None or self._loop is None:
            return
        try:
            from datetime import datetime, timezone
            data = {
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "module": record.module,
                "lineno": record.lineno,
                "func": record.funcName,
            }
            msg = {
                "type": "log",
                "data": data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            # 把广播任务投到主事件循环
            future = asyncio.run_coroutine_threadsafe(
                _ws_manager.broadcast("logs", msg),
                self._loop,
            )
            # 记录 future 中的异常（避免静默丢失）
            def _on_done(fut):
                try:
                    fut.result()
                except Exception as exc:
                    # 日志系统不能因自身报错而崩，只写 stderr
                    import sys
                    print(f"WS log broadcast failed: {exc}", file=sys.stderr)
            future.add_done_callback(_on_done)
        except Exception:
            # 日志本身不能因为广播失败而崩
            pass


# 单例
ws_log_handler = WsLogHandler()
