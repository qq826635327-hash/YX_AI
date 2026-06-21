"""任务日志服务：提供写日志和查询日志的接口。

支持两种模式：
1. 简单模式：write_task_log() — 写入文本日志（向后兼容）
2. 结构化模式：log_api_call() — 写入 API 调用的完整生命周期
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, List, Optional

from sqlmodel import Session, select

from app.core.trace import get_trace_id
from app.models.task_log import LOG_LEVELS, TaskLog

_logger = logging.getLogger(__name__)


def write_task_log(
    session: Session,
    task_id: str,
    level: str,
    message: str,
    data: Optional[str] = None,
    *,
    phase: Optional[str] = None,
    event_type: Optional[str] = None,
    data_json: Optional[dict] = None,
    trace_id: Optional[str] = None,
    push_ws: bool = True,
) -> TaskLog:
    """写入一条任务日志。

    Args:
        session: 数据库会话
        task_id: 任务 ID
        level: 日志级别（DEBUG / INFO / WARN / ERROR）
        message: 日志内容
        data: 附加数据（文本，向后兼容）
        phase: 阶段标记（generate / download / ref_collect / validate / system）
        event_type: 事件类型（api_request / ref_collect / download / validate / system）
        data_json: 结构化数据（JSON dict）
        trace_id: 请求追踪 ID（默认从上下文获取）
        push_ws: 是否通过 WS 推送到前端（默认 True）

    Returns:
        创建的 TaskLog 对象
    """
    if level not in LOG_LEVELS:
        level = "INFO"

    # 自动获取 trace_id
    if trace_id is None:
        trace_id = get_trace_id() or None

    log = TaskLog(
        task_id=task_id,
        level=level,
        message=message,
        data=data,
        phase=phase,
        event_type=event_type,
        data_json=data_json,
        trace_id=trace_id,
    )
    session.add(log)
    session.flush()

    # 通过 WS 推送到前端（ERROR/WARN 始终推送，其他级别按需推送）
    if push_ws and level in ("ERROR", "WARN", "WARNING", "INFO"):
        _push_log_ws(log)

    return log


def _push_log_ws(log: TaskLog) -> None:
    """将任务日志通过 WebSocket 推送到前端。"""
    try:
        from app.ws.routes import manager as ws_manager
        from datetime import datetime, timezone

        if ws_manager is None:
            return

        data = {
            "level": log.level,
            "logger": f"task:{log.task_id[:8]}",
            "message": log.message,
            "phase": log.phase,
            "event_type": log.event_type,
            "data_json": log.data_json,
            "trace_id": log.trace_id,
        }
        msg = {
            "type": "log",
            "data": data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.ensure_future(ws_manager.broadcast("logs", msg))
    except Exception:
        # WS 推送失败不应影响主流程
        pass


def log_api_call(
    session: Session,
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
) -> TaskLog:
    """记录一次 API 调用的完整生命周期。

    将请求/响应/耗时等结构化数据存入 data_json，
    同时生成人类可读的 message 摘要。

    Args:
        session: 数据库会话
        task_id: 任务 ID
        phase: 阶段（generate / download / ref_collect）
        provider_kind: Provider 标识（如 agnes）
        model: 模型名
        url: API URL
        method: HTTP 方法
        request_payload: 请求体（会自动脱敏）
        response_status: HTTP 状态码
        response_body: 响应体
        duration_ms: 耗时（毫秒）
        error: 错误信息
        trace_id: 追踪 ID（默认从上下文获取）

    Returns:
        创建的 TaskLog 对象
    """
    # 确定日志级别
    if error or (response_status is not None and response_status >= 400):
        level = "ERROR"
    elif response_status is not None and response_status >= 300:
        level = "WARN"
    else:
        level = "INFO"

    # 生成人类可读的 message
    msg_parts = [f"[{phase}]", method, _shorten_url(url)]
    if response_status is not None:
        msg_parts.append(f"→ {response_status}")
    if error:
        msg_parts.append(f"| Error: {error[:200]}")
    if duration_ms is not None:
        msg_parts.append(f"| {duration_ms}ms")
    message = " ".join(msg_parts)

    # 脱敏：移除 API Key 和过大的参考图数据
    safe_payload = _sanitize_payload(request_payload)

    # 脱敏响应体
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

    return write_task_log(
        session,
        task_id,
        level,
        message,
        phase=phase,
        event_type="api_request",
        data_json=data_json,
        trace_id=trace_id,
    )


def log_ref_collect(
    session: Session,
    task_id: str,
    *,
    source: str,
    count: int,
    details: Optional[list[dict]] = None,
    trace_id: Optional[str] = None,
) -> TaskLog:
    """记录参考图收集。"""
    message = f"[ref_collect] 从{source}收集到 {count} 张参考图"
    data_json = {
        "source": source,
        "count": count,
        "details": details or [],
    }
    return write_task_log(
        session, task_id, "INFO", message,
        phase="ref_collect", event_type="ref_collect",
        data_json=data_json, trace_id=trace_id,
    )


def log_download(
    session: Session,
    task_id: str,
    *,
    url: str,
    output_path: str,
    file_size: Optional[int] = None,
    duration_ms: Optional[int] = None,
    error: Optional[str] = None,
    trace_id: Optional[str] = None,
) -> TaskLog:
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
    return write_task_log(
        session, task_id, level, message,
        phase="download", event_type="download",
        data_json=data_json, trace_id=trace_id,
    )


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
            # 简要展示结构化数据
            for k, v in log.data_json.items():
                if k in ("request_payload", "response_body"):
                    # 大字段只展示类型
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

    # 移除 Authorization / api_key
    for key in ("api_key", "apiKey", "Authorization", "authorization"):
        if key in safe:
            safe[key] = "***REDACTED***"

    # 截断参考图 Data URI（太大了，只保留标记）
    _truncate_data_uris(safe)

    # 递归处理嵌套 dict
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
    # 保留完整结构，但截断过长的字符串
    return response


def _shorten_url(url: str) -> str:
    """缩短 URL 显示（只保留域名+路径前缀）。"""
    if len(url) > 80:
        return url[:77] + "..."
    return url
