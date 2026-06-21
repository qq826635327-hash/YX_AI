"""请求追踪模块 — 为每个任务执行周期分配唯一 trace_id。

使用 contextvars 在同一 asyncio 任务内共享 trace_id，
确保从收集参考图到 API 调用到下载结果，全链路日志可追踪。
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

# 每个任务执行周期内共享一个 trace_id
_current_trace_id: ContextVar[str] = ContextVar("trace_id", default="")


def new_trace_id() -> str:
    """生成新的 trace_id 并设置到当前上下文。"""
    tid = uuid.uuid4().hex[:12]
    _current_trace_id.set(tid)
    return tid


def get_trace_id() -> str:
    """获取当前上下文的 trace_id。"""
    return _current_trace_id.get()


def set_trace_id(trace_id: str) -> None:
    """设置当前上下文的 trace_id（用于恢复已有 trace）。"""
    _current_trace_id.set(trace_id)


def clear_trace_id() -> None:
    """清除当前上下文的 trace_id。"""
    _current_trace_id.set("")
