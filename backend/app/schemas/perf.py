"""性能监控 API 的 Schema。"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PerfMeasureAggregateIn(BaseModel):
    name: str
    count: int
    totalMs: float
    avgMs: float
    p95Ms: float
    maxMs: float


class PerfEventIn(BaseModel):
    seq: int
    ts: int
    kind: str
    name: str
    durationMs: Optional[float] = None
    payload: Optional[dict] = None


class PerfSummaryIn(BaseModel):
    sessionDurationS: int
    longTaskCount: int
    longTaskTotalMs: float
    memUsedMB: int
    memTotalMB: Optional[int] = None
    memLimitMB: Optional[int] = None
    counters: dict = Field(default_factory=dict)
    measureAggregates: list[PerfMeasureAggregateIn] = Field(default_factory=list)


class PerfSessionCreate(BaseModel):
    sessionId: str
    startedAt: Optional[str] = None
    endedAt: Optional[str] = None
    ua: Optional[str] = None
    appVersion: Optional[str] = None
    summary: PerfSummaryIn
    counters: dict = Field(default_factory=dict)
    measureAggregates: list[PerfMeasureAggregateIn] = Field(default_factory=list)
    events: list[PerfEventIn] = Field(default_factory=list)


class PerfSessionOut(BaseModel):
    id: str
    session_id: str
    started_at: Optional[str]
    ended_at: Optional[str]
    app_version: Optional[str]
    session_duration_s: int
    long_task_count: int
    long_task_total_ms: float
    mem_used_mb: int
    mem_total_mb: Optional[int]
    mem_limit_mb: Optional[int] = None
    counters: Optional[dict]
    measure_aggregates: Optional[list]
    created_at: datetime

    class Config:
        from_attributes = True


class PerfAlertOut(BaseModel):
    id: str
    session_id: str
    level: str
    metric: str
    threshold: float
    actual: float
    message: str
    acknowledged: bool
    created_at: datetime

    class Config:
        from_attributes = True


class PerfDiagnoseFinding(BaseModel):
    id: str
    severity: str  # overall / warning / error / critical
    category: str
    title: str
    evidence: str = ""
    suggestion: str = ""
    suspects: list[str] = Field(default_factory=list)


class PerfDiagnoseResponse(BaseModel):
    session_id: str
    severity: str
    findings: list[PerfDiagnoseFinding]
    report: dict  # 完整原始报告，供复制喂给任意 AI
