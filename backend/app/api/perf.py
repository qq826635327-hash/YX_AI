"""性能监控 API。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_session
from app.schemas.perf import PerfAlertOut, PerfSessionCreate, PerfSessionOut
from app.services.perf_service import (
    acknowledge_alert,
    clear_all,
    diagnose_session,
    ingest_session,
    list_alerts,
    list_sessions,
)
from app.ws.routes import manager, make_message

router = APIRouter(prefix="/perf", tags=["performance"])

logger = logging.getLogger(__name__)


@router.post("/sessions", response_model=dict)
async def create_perf_session(
    data: PerfSessionCreate,
    db: Session = Depends(get_session),
):
    """接收前端上报的性能会话数据。"""
    session_id, alerts = ingest_session(db, data)

    # 实时推送告警到前端；推送失败不应影响 API 返回
    try:
        for alert in alerts:
            await manager.broadcast(
                "perf",
                make_message(
                    "perf.alert",
                    {
                        "session_id": alert.session_id,
                        "level": alert.level,
                        "metric": alert.metric,
                        "message": alert.message,
                        "actual": alert.actual,
                        "threshold": alert.threshold,
                    },
                ),
            )
    except Exception:
        logger.exception("Failed to broadcast perf alerts")

    return {"session_id": session_id, "alert_count": len(alerts)}


@router.get("/sessions", response_model=list[PerfSessionOut])
async def get_perf_sessions(
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_session),
):
    """查询历史性能会话列表。"""
    return list_sessions(db, limit=limit, offset=offset)


@router.get("/alerts", response_model=list[PerfAlertOut])
async def get_perf_alerts(
    limit: int = 50,
    offset: int = 0,
    acknowledged: Optional[bool] = None,
    db: Session = Depends(get_session),
):
    """查询性能告警。"""
    return list_alerts(db, limit=limit, offset=offset, acknowledged=acknowledged)


@router.post("/alerts/{alert_id}/acknowledge", response_model=Optional[PerfAlertOut])
async def ack_perf_alert(alert_id: str, db: Session = Depends(get_session)):
    """标记告警已处理。"""
    return acknowledge_alert(db, alert_id)


@router.delete("/clear", response_model=dict)
async def clear_perf_data(db: Session = Depends(get_session)):
    """清空所有性能监控数据。"""
    return clear_all(db)


@router.post("/diagnose")
async def diagnose_perf_session(
    payload: dict,
    db: Session = Depends(get_session),
):
    """对指定性能会话做 AI 根因分析，返回结构化诊断报告。

    请求体: {"session_id": "..."}
    返回: {severity, findings[], report} —— findings 供前端展示，report 可复制喂给任意 AI。
    """
    session_id = payload.get("session_id")
    if not session_id:
        return {"error": "session_id is required"}
    return diagnose_session(db, session_id)


@router.get("/queue-depth")
async def get_perf_queue_depth():
    """暴露任务队列深度（供性能面板展示后端饱和度）。"""
    from app.services.perf_service import get_queue_depth
    from app.schemas.common import ok
    return ok(get_queue_depth())
