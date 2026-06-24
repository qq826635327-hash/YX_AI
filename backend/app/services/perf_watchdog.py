"""事件循环 watchdog：检测 asyncio 事件循环被同步阻塞。

原理：用 loop.call_later 安排一个周期性回调，正常情况下每 CHECK_INTERVAL 秒触发一次。
若回调触发时刻与预期时刻的漂移超过 BLOCK_THRESHOLD 秒，说明事件循环在这段时间内被
同步代码阻塞（如同步 IO、CPU 密集计算、未走 run_in_executor 的阻塞调用）。

漂移超过阈值时记录一条 perf 告警，并经 WebSocket 实时推送到前端。
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Optional

from app.ws.routes import manager, make_message

logger = logging.getLogger(__name__)

CHECK_INTERVAL = 0.2  # 每 200ms 检查一次
BLOCK_THRESHOLD = 0.2  # 漂移超过 200ms 判定为主线程阻塞

_handle: Optional[asyncio.TimerHandle] = None
_last_expected = 0.0
_last_report_ts = 0.0
_REPORT_COOLDOWN = 5.0  # 同类告警冷却 5 秒，避免刷屏


async def _watchdog_tick(expected_ts: float) -> None:
    """watchdog 单次回调：比较实际触发时刻与预期时刻的漂移。"""
    global _last_expected, _last_report_ts

    now = time.monotonic()
    drift = now - expected_ts
    _last_expected = now + CHECK_INTERVAL

    if drift > BLOCK_THRESHOLD:
        wall_now = time.time()
        if wall_now - _last_report_ts > _REPORT_COOLDOWN:
            _last_report_ts = wall_now
            duration_ms = round(drift * 1000)
            logger.warning(
                "事件循环阻塞 %.0fms（漂移 %.3fs > 阈值 %.2fs），可能存在同步阻塞调用",
                duration_ms,
                drift,
                BLOCK_THRESHOLD,
            )
            # 实时推送告警到前端 perf 频道
            try:
                await manager.broadcast(
                    "perf",
                    make_message(
                        "perf.alert",
                        {
                            "session_id": "backend",
                            "level": "error",
                            "metric": "eventloop.blocked",
                            "threshold": round(BLOCK_THRESHOLD * 1000),
                            "actual": duration_ms,
                            "message": f"后端事件循环阻塞 {duration_ms}ms，可能存在同步阻塞调用拖慢所有请求",
                        },
                    ),
                )
            except Exception:
                logger.debug("watchdog 告警推送失败", exc_info=True)

    # 安排下一次回调
    global _handle
    loop = asyncio.get_running_loop()
    _handle = loop.call_later(CHECK_INTERVAL, lambda: asyncio.ensure_future(_watchdog_tick(_last_expected)))


def start_watchdog() -> None:
    """启动事件循环 watchdog。在 lifespan 启动阶段调用。"""
    global _last_expected, _last_report_ts, _handle
    if _handle is not None:
        return  # 已启动
    loop = asyncio.get_running_loop()
    _last_expected = time.monotonic() + CHECK_INTERVAL
    _last_report_ts = time.time()
    _handle = loop.call_later(CHECK_INTERVAL, lambda: asyncio.ensure_future(_watchdog_tick(_last_expected)))
    logger.info(f"事件循环 watchdog 已启动（检测间隔 {CHECK_INTERVAL}s，阈值 {BLOCK_THRESHOLD}s）")


def stop_watchdog() -> None:
    """停止事件循环 watchdog。在 lifespan 关闭阶段调用。"""
    global _handle
    if _handle is not None:
        _handle.cancel()
        _handle = None
        logger.info("事件循环 watchdog 已停止")
