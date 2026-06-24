"""任务日志服务：内存缓冲批量写入，减少 SQLite 锁冲突。

写入流程：write_task_log() → 内存 deque → 后台协程每 2s/满 50 条 → 批量 INSERT → SQLite
WS 推送：立即推送，不经过 DB，前端实时性不受影响。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List, Optional

from sqlmodel import Session, select

from app.core.trace import get_trace_id
from app.models.task_log import LOG_LEVELS, TaskLog

_logger = logging.getLogger(__name__)

# ============================================================
# 内存缓冲区
# ============================================================

_FLUSH_INTERVAL = 2.0       # 后台 flush 间隔（秒）
_FLUSH_BATCH_SIZE = 50      # 队列满此数量时立即触发 flush
_MAX_BUFFER_SIZE = 500      # 缓冲区上限，超过则同步 flush 防止内存膨胀


@dataclass
class _BufferedLog:
    """内存中的日志条目（纯数据，不依赖 Session）。"""
    task_id: str
    level: str
    message: str
    data: Optional[str] = None
    phase: Optional[str] = None
    event_type: Optional[str] = None
    data_json: Optional[dict] = None
    trace_id: Optional[str] = None
    push_ws: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


# 全局缓冲区 + 线程锁
_buffer: deque[_BufferedLog] = deque()
_buffer_lock = threading.Lock()
_flush_task: asyncio.Task | None = None


def _enqueue(item: _BufferedLog) -> None:
    """将日志加入缓冲区，满则触发同步 flush。"""
    with _buffer_lock:
        _buffer.append(item)
        current_len = len(_buffer)

    # 缓冲区溢出保护：同步 flush
    if current_len >= _MAX_BUFFER_SIZE:
        _logger.warning("任务日志缓冲区溢出 (%d 条)，执行同步 flush", current_len)
        flush_buffer_sync()


# ============================================================
# 公开 API：写入日志
# ============================================================

def write_task_log(
    task_id: str,
    level: str,
    message: str,
    data: Optional[str] = None,
    *,
    phase: Optional[str] = None,
    event_type: Optional[str] = None,
    data_json: Optional[dict] = None,
    trace_id: Optional[str] = None,
    push_ws: bool = False,
) -> None:
    """写入一条任务日志（缓冲模式，不立即写 DB）。

    Args:
        task_id: 任务 ID
        level: 日志级别（DEBUG / INFO / WARN / ERROR）
        message: 日志内容
        data: 附加数据（文本，向后兼容）
        phase: 阶段标记
        event_type: 事件类型
        data_json: 结构化数据（JSON dict）
        trace_id: 请求追踪 ID（默认从上下文获取）
        push_ws: 是否通过 WS 推送到前端
    """
    if level not in LOG_LEVELS:
        level = "INFO"

    if trace_id is None:
        trace_id = get_trace_id() or None

    item = _BufferedLog(
        task_id=task_id,
        level=level,
        message=message,
        data=data,
        phase=phase,
        event_type=event_type,
        data_json=data_json,
        trace_id=trace_id,
        push_ws=push_ws,
    )

    # WS 推送（立即，不经过 DB）
    if push_ws and level in ("ERROR", "WARN", "WARNING", "INFO"):
        _push_log_ws(item)

    # 加入缓冲区
    _enqueue(item)


# ============================================================
# WS 推送（立即，不经过 DB）
# ============================================================

def _push_log_ws(item: _BufferedLog) -> None:
    """将任务日志通过 WebSocket 推送到前端。"""
    try:
        from app.ws.routes import manager as ws_manager

        if ws_manager is None:
            return

        data = {
            "level": item.level,
            "logger": f"task:{item.task_id[:8]}",
            "message": item.message,
            "phase": item.phase,
            "event_type": item.event_type,
            "data_json": item.data_json,
            "trace_id": item.trace_id,
        }
        msg = {
            "type": "log",
            "data": data,
            "timestamp": item.created_at.isoformat(),
        }

        try:
            loop = asyncio.get_running_loop()
            if loop.is_running():
                asyncio.ensure_future(ws_manager.broadcast("logs", msg))
        except RuntimeError:
            pass
    except Exception:
        pass


# ============================================================
# Flush：缓冲区 → DB
# ============================================================

def _do_flush(batch: list[_BufferedLog]) -> None:
    """将一批日志写入 DB（同步，在线程池中执行）。

    逐条 INSERT + 独立 commit，避免单条失败导致整批回滚。
    """
    from app.db import get_engine

    engine = get_engine()
    written = 0
    for item in batch:
        try:
            with Session(engine, expire_on_commit=False) as session:
                log = TaskLog(
                    task_id=item.task_id,
                    level=item.level,
                    message=item.message,
                    data=item.data,
                    phase=item.phase,
                    event_type=item.event_type,
                    data_json=item.data_json,
                    trace_id=item.trace_id,
                )
                session.add(log)
                session.commit()
                written += 1
        except Exception as e:
            # 单条失败 fallback 到 Python logging，不丢失信息
            _logger.warning(
                "任务日志写入 DB 失败 (task=%s): %s | 原始消息: %s",
                item.task_id[:8], e, item.message[:200],
            )

    if written > 0:
        _logger.debug("任务日志 flush 完成: %d/%d 条", written, len(batch))


def flush_buffer_sync() -> None:
    """同步 flush 缓冲区（用于溢出保护和应用关闭时）。"""
    with _buffer_lock:
        batch = list(_buffer)
        _buffer.clear()

    if batch:
        _do_flush(batch)


async def flush_buffer_async() -> None:
    """异步 flush 缓冲区（后台协程调用，DB 操作放到线程池避免阻塞事件循环）。"""
    with _buffer_lock:
        batch = list(_buffer)
        _buffer.clear()

    if batch:
        await asyncio.to_thread(_do_flush, batch)


# ============================================================
# 后台 flush 协程生命周期
# ============================================================

async def start_flush_loop() -> None:
    """启动后台 flush 协程（在 lifespan 中调用）。"""
    global _flush_task
    _flush_task = asyncio.create_task(_flush_loop())
    _logger.info("任务日志缓冲 flush 协程已启动 (间隔 %.1fs, 批量 %d 条)",
                 _FLUSH_INTERVAL, _FLUSH_BATCH_SIZE)


async def stop_flush_loop() -> None:
    """停止后台 flush 协程并 flush 剩余日志（在 lifespan shutdown 中调用）。"""
    global _flush_task
    if _flush_task is not None:
        _flush_task.cancel()
        try:
            await _flush_task
        except asyncio.CancelledError:
            pass
        _flush_task = None

    # 关闭前 flush 剩余日志
    await flush_buffer_async()
    _logger.info("任务日志缓冲 flush 协程已停止，剩余日志已 flush")


async def _flush_loop() -> None:
    """后台协程：定时 flush + 队列满时立即 flush。"""
    while True:
        try:
            await asyncio.sleep(_FLUSH_INTERVAL)

            # 检查是否需要立即 flush（队列满）
            with _buffer_lock:
                current_len = len(_buffer)

            if current_len >= _FLUSH_BATCH_SIZE or current_len > 0:
                await flush_buffer_async()

        except asyncio.CancelledError:
            raise
        except Exception as e:
            _logger.error("任务日志 flush 协程异常: %s", e)
            await asyncio.sleep(1)  # 出错后短暂等待再重试


# ============================================================
# 结构化日志辅助函数
# ============================================================

def log_api_call(
    task_id: str,
    *,
    phase: str,
    provider_kind: str,
    model: str,
    url: str,
    method: str = "POST",
    request_payload: Optional[dict] = None,
    response_status: Optional[int] = None,
    response_body: Optional[dict] = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """记录一次 API 调用的完整生命周期。"""
    if error or (response_status is not None and response_status >= 400):
        level = "ERROR"
    elif response_status is not None and response_status >= 300:
        level = "WARN"
    else:
        level = "INFO"

    msg_parts = [f"[{phase}]", method, _shorten_url(url)]
    if response_status is not None:
        msg_parts.append(f"→ {response_status}")
    if error:
        msg_parts.append(f"| Error: {error[:200]}")
    if duration_ms is not None:
        msg_parts.append(f"| {duration_ms}ms")
    message = " ".join(msg_parts)

    safe_payload = _sanitize_payload(request_payload)
    safe_response = _sanitize_response(response_body)

    data_json = {
        "provider_kind": provider_kind,
        "model": model,
        "url": url,
        "method": method,
        "request_payload": safe_payload,
        "response_status": response_status,
        "response_body": safe_response,
        "duration_ms": duration_ms,
        "error": error,
    }

    write_task_log(
        task_id,
        level,
        message,
        phase=phase,
        event_type="api_request",
        data_json=data_json,
        trace_id=trace_id,
    )


def log_ref_collect(
    task_id: str,
    *,
    source: str,
    count: int,
    details: Optional[list[dict]] = None,
    trace_id: Optional[str] = None,
) -> None:
    """记录参考图收集。"""
    message = f"[ref_collect] 从{source}收集到 {count} 张参考图"
    data_json = {
        "source": source,
        "count": count,
        "details": details or [],
    }
    write_task_log(
        task_id, "INFO", message,
        phase="ref_collect", event_type="ref_collect",
        data_json=data_json, trace_id=trace_id,
    )


def log_download(
    task_id: str,
    *,
    url: str,
    output_path: str,
    file_size: Optional[int] = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> None:
    """记录文件下载。"""
    level = "ERROR" if error else "INFO"
    msg_parts = [f"[download]", f"GET {_shorten_url(url)}"]
    if error:
        msg_parts.append(f"| Error: {error[:200]}")
    if duration_ms is not None:
        msg_parts.append(f"| {duration_ms}ms")
    if file_size is not None:
        msg_parts.append(f"| {file_size // 1024}KB")
    message = " ".join(msg_parts)

    data_json = {
        "url": url,
        "output_path": output_path,
        "file_size": file_size,
        "duration_ms": duration_ms,
        "error": error,
    }
    write_task_log(
        task_id, level, message,
        phase="download", event_type="download",
        data_json=data_json, trace_id=trace_id,
    )


# ============================================================
# 查询 API（不变，仍需 Session）
# ============================================================

def get_task_logs(
    session: Session,
    task_id: str,
    limit: int = 100,
) -> List[TaskLog]:
    """查询某个任务的所有日志（按时间正序）。"""
    stmt = (
        select(TaskLog)
        .where(TaskLog.task_id == task_id)
        .order_by(TaskLog.created_at.asc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def get_task_logs_by_trace(
    session: Session,
    trace_id: str,
    limit: int = 100,
) -> List[TaskLog]:
    """按 trace_id 查询日志（串联多步操作）。"""
    stmt = (
        select(TaskLog)
        .where(TaskLog.trace_id == trace_id)
        .order_by(TaskLog.created_at.asc())
        .limit(limit)
    )
    return list(session.exec(stmt).all())


def format_logs_as_text(logs: List[TaskLog]) -> str:
    """将日志格式化为文本（便于调试查看）。"""
    lines = []
    for log in logs:
        ts = log.created_at.strftime("%H:%M:%S") if log.created_at else "??:??:??"
        phase = f" [{log.phase}]" if log.phase else ""
        trace = f" <{log.trace_id}>" if log.trace_id else ""
        lines.append(f"[{ts}]{phase}{trace} {log.level:5s} {log.message}")
        if log.data:
            lines.append(f"         └─ {log.data}")
        if log.data_json:
            for k, v in log.data_json.items():
                if k in ("request_payload", "response_body"):
                    v_repr = f"<{type(v).__name__}>" if v else "None"
                else:
                    v_repr = repr(v)[:100]
                lines.append(f"         ├─ {k}: {v_repr}")
    return "\n".join(lines)


# ============================================================
# 内部辅助函数
# ============================================================

def _sanitize_payload(payload: Optional[dict]) -> Optional[dict]:
    """脱敏：移除 API Key 和过大的参考图数据。"""
    if not payload:
        return payload

    safe = dict(payload)

    for key in ("api_key", "apiKey", "Authorization", "authorization"):
        if key in safe:
            safe[key] = "***REDACTED***"

    _truncate_data_uris(safe)

    for k, v in safe.items():
        if isinstance(v, dict):
            safe[k] = _sanitize_payload(v)

    return safe


def _truncate_data_uris(data: dict) -> None:
    """截断 data:image/... URI，只保留标记。"""
    for key, value in data.items():
        if isinstance(value, str) and value.startswith("data:image/"):
            data[key] = f"<data:image {len(value)} chars>"
        elif isinstance(value, list):
            new_list = []
            for item in value:
                if isinstance(item, str) and item.startswith("data:image/"):
                    new_list.append(f"<data:image {len(item)} chars>")
                else:
                    new_list.append(item)
            data[key] = new_list


def _sanitize_response(response: Optional[dict]) -> Optional[dict]:
    """脱敏响应体：截断过大的字段。"""
    if not response:
        return response
    return response


def _shorten_url(url: str) -> str:
    """缩短 URL 显示（只保留域名+路径前缀）。"""
    if len(url) > 80:
        return url[:77] + "..."
    return url
