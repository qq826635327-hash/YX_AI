"""性能监控相关模型。"""

from typing import Optional
from sqlalchemy import JSON, Column, Index, UniqueConstraint
from sqlmodel import Field

from app.models.base import IDMixin, TimestampMixin


class PerfSession(IDMixin, TimestampMixin, table=True):
    """前端性能监控会话聚合表。"""

    __tablename__ = "perf_sessions"

    session_id: str = Field(unique=True, index=True, max_length=64, description="前端生成的会话 ID")
    started_at: Optional[str] = Field(default=None, description="会话开始时间 ISO")
    ended_at: Optional[str] = Field(default=None, description="会话结束时间 ISO")
    ua: Optional[str] = Field(default=None, max_length=500)
    app_version: Optional[str] = Field(default=None, max_length=50)

    # 聚合摘要
    session_duration_s: int = Field(default=0)
    long_task_count: int = Field(default=0)
    long_task_total_ms: float = Field(default=0)
    mem_used_mb: int = Field(default=0)
    mem_total_mb: Optional[int] = Field(default=None)
    mem_limit_mb: Optional[int] = Field(default=None, description="浏览器 JS 堆上限（jsHeapSizeLimit）")

    # 计数器快照 + measure 聚合
    counters: Optional[dict] = Field(default=None, sa_column=Column(JSON))
    measure_aggregates: Optional[list] = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (
        Index("ix_perf_sessions_created_at", "created_at"),
    )


class PerfEvent(IDMixin, TimestampMixin, table=True):
    """原始性能事件（抽样存储）。"""

    __tablename__ = "perf_events"

    session_id: str = Field(index=True, max_length=64)
    seq: int = Field(default=0)
    ts: int = Field(description="前端时间戳 ms")
    kind: str = Field(max_length=20)  # mark/measure/counter/longtask/paint/memory
    name: str = Field(max_length=120, index=True)
    duration_ms: Optional[float] = Field(default=None)
    payload: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    __table_args__ = (
        Index("ix_perf_events_session_seq", "session_id", "seq"),
        UniqueConstraint("session_id", "seq", name="uq_perf_events_session_seq"),
    )


class PerfAlert(IDMixin, TimestampMixin, table=True):
    """性能告警记录。"""

    __tablename__ = "perf_alerts"

    session_id: str = Field(index=True, max_length=64)
    level: str = Field(max_length=20)  # warning / error
    metric: str = Field(max_length=50)
    threshold: float
    actual: float
    message: str = Field(max_length=500)
    acknowledged: bool = Field(default=False)

    __table_args__ = (
        Index("ix_perf_alerts_created_at", "created_at"),
    )
