"""日志查询 API。

为前端 / AI 开发助手提供：
- `GET /api/logs` 读取 `logs/backend.log` 历史日志，支持按 level 过滤
- `GET /api/logs/info` 获取日志文件元信息（路径、大小、最后修改时间）
- `DELETE /api/logs/clear` 清空日志文件（开发模式）
- `GET /api/logs/tasks/{task_id}` 获取任务的结构化日志（从 DB 读取）
"""

from __future__ import annotations

import logging
import os
import re
from collections import deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, HTTPException, Path as PathParam, Query
from pydantic import BaseModel

from app.core.config import get_settings
from app.db import session_scope
from app.schemas.common import ok

router = APIRouter(prefix="/logs", tags=["logs"])

# 解析日志行
# 典型格式: 2026-06-20 14:33:21 [app.api.characters] ERROR: something went wrong
_LOG_PATTERN = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}(?:,\d+)?)\s+"
    r"\[(?P<logger>[^\]]+)\]\s+"
    r"(?P<level>DEBUG|INFO|WARNING|ERROR|CRITICAL):\s+"
    r"(?P<message>.*)$"
)


class LogEntry(BaseModel):
    """单条日志条目。"""

    timestamp: str  # ISO8601
    level: str
    logger: str
    message: str


class LogListResponse(BaseModel):
    """日志查询响应。"""

    total: int
    returned: int
    file: str
    entries: List[LogEntry]


def _get_log_file() -> Path:
    """获取日志文件绝对路径。"""
    settings = get_settings()
    log_dir = Path(settings.app.logs_dir)
    if not log_dir.is_absolute():
        log_dir = settings.backend_root / log_dir
    return log_dir / "backend.log"


def _tail_lines(f, max_lines: int) -> list[str]:
    """从文件对象读取末尾 max_lines 行，避免全量加载大文件。

    对大文件使用反向 seek 分块读取；对小文件直接用 deque。
    """
    # 先尝试获取文件大小，决定策略
    try:
        f.seek(0, 2)  # seek to end
        file_size = f.tell()
    except (OSError, IOError):
        f.seek(0)
        return list(deque(f, maxlen=max_lines))

    # 小文件（< 1MB）直接全量读末尾
    if file_size < 1024 * 1024:
        f.seek(0)
        return list(deque(f, maxlen=max_lines))

    # 大文件：从末尾分块反向读取，直到收集到 max_lines 行
    chunk_size = 64 * 1024  # 64KB chunks
    lines: deque = deque(maxlen=max_lines)
    pos = file_size
    leftover = ""

    while pos > 0 and len(lines) < max_lines:
        read_size = min(chunk_size, pos)
        pos -= read_size
        f.seek(pos)
        chunk = f.read(read_size)
        if not chunk:
            break
        # 把 leftover 拼到 chunk 末尾（因为这是更早的内容）
        data = chunk + leftover
        parts = data.split("\n")
        # 第一段可能不完整（除非 pos == 0），保留到下一轮
        if pos > 0:
            leftover = parts[0]
            parts = parts[1:]
        else:
            leftover = ""
        # parts 是从早到晚的行，逆序加入 deque（deque 会自动保留末尾 max_lines 行）
        for line in reversed(parts):
            lines.appendleft(line)

    if leftover:
        lines.appendleft(leftover)

    return list(lines)


def _parse_log_line(line: str) -> Optional[LogEntry]:
    """把单行日志解析为 LogEntry；解析失败返回 None。"""
    line = line.rstrip("\n").rstrip("\r")
    if not line.strip():
        return None
    m = _LOG_PATTERN.match(line)
    if not m:
        return None
    try:
        # 把 "2026-06-20 14:33:21" 转成 ISO 格式
        ts_str = m.group("ts")
        for fmt in ("%Y-%m-%d %H:%M:%S,%f", "%Y-%m-%d %H:%M:%S"):
            try:
                dt = datetime.strptime(ts_str, fmt)
                break
            except ValueError:
                continue
        else:
            return None
        # 日志文件里的 %(asctime)s 是服务器本地时间，但没有时区标记。
        # 之前直接 + "Z" 当成 UTC，导致前端显示错 8 小时。
        # 修正：把 naive datetime 解释成本地时间，然后转成带时区 ISO。
        try:
            local_dt = dt.astimezone()
            timestamp = local_dt.isoformat()
        except Exception:
            # 兜底：直接附加本地时区偏移
            local_offset = datetime.now().astimezone().utcoffset()
            if local_offset is None:
                local_offset = timezone.utc.utcoffset(datetime.now()) or timedelta(0)
            timestamp = dt.replace(tzinfo=timezone(local_offset)).isoformat()
        return LogEntry(
            timestamp=timestamp,
            level=m.group("level"),
            logger=m.group("logger"),
            message=m.group("message"),
        )
    except Exception:
        return None


@router.get("")
async def list_logs(
    level: Optional[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]] = Query(
        None, description="按级别过滤（不传则返回全部）"
    ),
    limit: int = Query(200, ge=1, le=2000, description="最多返回多少条"),
    offset: int = Query(0, ge=0, description="从尾部倒序的偏移"),
    keyword: Optional[str] = Query(None, description="按关键字过滤（message 子串）"),
):
    """读取历史日志。

    说明：日志可能很大，倒序读末尾的 `offset..offset+limit` 行。
    返回格式与项目其他 API 一致：{ "data": LogListResponse, "message": ... }
    """
    log_file = _get_log_file()
    if not log_file.exists():
        return ok(LogListResponse(total=0, returned=0, file=str(log_file), entries=[]).model_dump())

    try:
        # 高效读取：只读文件末尾部分，避免大文件全量加载
        max_lines = offset + limit + 500  # 多读一些，因为解析会丢弃部分行
        with open(log_file, "r", encoding="utf-8", errors="replace") as f:
            # 从文件末尾向前读取
            lines = _tail_lines(f, max_lines)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取日志文件失败: {e}")

    # 倒序（最新的在前）
    lines.reverse()

    parsed: List[LogEntry] = []
    for line in lines:
        entry = _parse_log_line(line)
        if entry is None:
            continue
        if level and entry.level != level:
            continue
        if keyword and keyword.lower() not in entry.message.lower():
            continue
        parsed.append(entry)

    total = len(parsed)
    sliced = parsed[offset : offset + limit]
    return ok(
        LogListResponse(
            total=total,
            returned=len(sliced),
            file=str(log_file),
            entries=sliced,
        ).model_dump()
    )


@router.get("/info")
async def log_info():
    """返回日志文件元信息。"""
    log_file = _get_log_file()
    st = log_file.stat() if log_file.exists() else None
    info = {
        "file": str(log_file),
        "exists": st is not None,
        "size_bytes": st.st_size if st else 0,
        "modified_at": datetime.fromtimestamp(st.st_mtime, tz=timezone.utc).isoformat() if st else None,
    }
    return ok(info)


@router.delete("/clear")
async def clear_logs():
    """清空日志文件。仅用于开发调试。"""
    env = os.getenv("ADS_ENV", "development")
    if env != "development":
        raise HTTPException(status_code=403, detail="生产环境禁止清空日志")

    log_file = _get_log_file()
    if log_file.exists():
        try:
            # 截断文件而不是删除（避免 FileHandler 句柄失效）
            with open(log_file, "w", encoding="utf-8") as f:
                pass  # "w" 模式已自动截断为 0 字节
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"清空日志失败: {e}")
    # 写一条标记
    logging.getLogger(__name__).info("=== 日志已被清空 ===")
    return ok({"ok": True, "file": str(log_file)})


# ============================================================
# 任务结构化日志 API（从 DB 读取）
# ============================================================


class TaskLogEntry(BaseModel):
    """任务日志条目（含结构化数据）。"""
    id: str
    task_id: str
    level: str
    message: str
    phase: Optional[str] = None
    event_type: Optional[str] = None
    data_json: Optional[Dict[str, Any]] = None
    trace_id: Optional[str] = None
    data: Optional[str] = None
    created_at: Optional[str] = None


class TaskLogListResponse(BaseModel):
    """任务日志列表响应。"""
    task_id: str
    trace_id: Optional[str] = None
    total: int
    entries: List[TaskLogEntry]


@router.get("/tasks/{task_id}")
async def get_task_logs(
    task_id: str = PathParam(..., description="任务 ID"),
    level: Optional[Literal["DEBUG", "INFO", "WARN", "ERROR"]] = Query(None, description="按级别过滤"),
    phase: Optional[str] = Query(None, description="按阶段过滤（generate/download/ref_collect/validate/system）"),
    limit: int = Query(200, ge=1, le=1000, description="最多返回条数"),
):
    """获取任务的结构化日志（从 DB 读取）。

    返回该任务的所有日志，包含结构化数据（API 请求/响应/耗时等）。
    """
    from app.services.task_log_service import get_task_logs as _get_task_logs

    with session_scope() as session:
        logs = _get_task_logs(session, task_id, limit=limit * 3)  # 多读一些用于过滤

    # 过滤
    filtered = logs
    if level:
        filtered = [l for l in filtered if l.level == level]
    if phase:
        filtered = [l for l in filtered if l.phase == phase]

    # 截断
    filtered = filtered[:limit]

    # 提取 trace_id（取第一条非空的）
    trace_id = None
    for l in filtered:
        if l.trace_id:
            trace_id = l.trace_id
            break

    entries = [
        TaskLogEntry(
            id=l.id,
            task_id=l.task_id,
            level=l.level,
            message=l.message,
            phase=l.phase,
            event_type=l.event_type,
            data_json=l.data_json,
            trace_id=l.trace_id,
            data=l.data,
            created_at=l.created_at.isoformat() if l.created_at else None,
        )
        for l in filtered
    ]

    return ok(
        TaskLogListResponse(
            task_id=task_id,
            trace_id=trace_id,
            total=len(entries),
            entries=entries,
        ).model_dump()
    )
