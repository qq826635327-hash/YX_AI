"""TaskLog 模型：任务执行日志（支持结构化数据）。"""

from datetime import datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


# 日志级别
LOG_LEVELS = ("DEBUG", "INFO", "WARN", "ERROR")

# 事件类型
EVENT_TYPES = (
    "api_request",    # API 调用（请求+响应）
    "ref_collect",    # 参考图收集
    "download",       # 文件下载
    "validate",       # 参数校验
    "system",         # 系统事件（启动/停止等）
)


class TaskLog(IDMixin, TimestampMixin, table=True):
    """任务日志表（扩展版：支持结构化数据和请求追踪）。"""

    __tablename__ = "task_logs"

    task_id: str = Field(
        foreign_key="generation_tasks.id",
        index=True,
        max_length=36,
        ondelete="CASCADE",
        description="关联的任务 ID",
    )
    level: str = Field(
        max_length=10,
        description="日志级别：DEBUG / INFO / WARN / ERROR",
    )
    message: str = Field(
        description="日志内容",
    )

    # ── 新增：结构化数据字段 ──
    phase: Optional[str] = Field(
        default=None,
        max_length=30,
        description="阶段标记：generate / download / ref_collect / validate / system",
    )
    event_type: Optional[str] = Field(
        default=None,
        max_length=30,
        description="事件类型：api_request / ref_collect / download / validate / system",
    )
    data_json: Optional[dict] = Field(
        default=None,
        description="结构化数据（JSON），如 API 请求/响应详情",
        sa_column=Column(JSON, nullable=True),
    )
    trace_id: Optional[str] = Field(
        default=None,
        max_length=20,
        index=True,
        description="请求追踪 ID，串联同一任务的多步操作",
    )

    # ── 向后兼容：保留 data 文本字段 ──
    data: Optional[str] = Field(
        default=None,
        description="附加数据（文本，向后兼容）",
    )
