"""任务中心 API 路由。"""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.schemas.common import ok, paginate
from app.services.generation_service import clear_tasks, get_task, list_tasks
from app.services.task_log_service import get_task_logs

router = APIRouter(prefix="/tasks", tags=["tasks"])


class TaskClearRequest(BaseModel):
    """批量清理任务请求。"""

    project_id: Optional[str] = None
    status: Optional[str] = None  # 逗号分隔，如 "succeeded,failed,cancelled"


@router.get("")
async def api_list_tasks(
    project_id: Optional[str] = Query(default=None),
    status: Optional[str] = Query(default=None, description="任务状态，多个用逗号分隔（如 pending,running）"),
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    session: Session = Depends(get_session),
):
    """任务列表（支持多状态过滤，逗号分隔）。"""
    # 解析多状态过滤
    status_list = None
    if status:
        status_list = [s.strip() for s in status.split(",") if s.strip()]

    items, total = list_tasks(
        session,
        project_id=project_id,
        status=status_list,
        target_type=target_type,
        target_id=target_id,
        page=page,
        page_size=page_size,
    )
    return paginate(serialize_models(items), total, page, page_size)


# 固定路径路由必须在动态路径 /{task_id} 之前，否则 /clear 会被当作 task_id
@router.post("/clear")
async def api_clear_tasks(
    req: TaskClearRequest,
    session: Session = Depends(get_session),
):
    """批量清理任务（默认清理已结束任务）。"""
    status_list = None
    if req.status:
        status_list = [s.strip() for s in req.status.split(",") if s.strip()]
    count = clear_tasks(session, project_id=req.project_id, status=status_list)
    return ok({"cleared": count})


@router.get("/{task_id}")
async def api_get_task(task_id: str, session: Session = Depends(get_session)):
    """任务详情。"""
    task = get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})
    return ok(serialize_model(task))


@router.get("/{task_id}/logs")
async def api_get_task_logs(
    task_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    session: Session = Depends(get_session),
):
    """获取任务的执行日志（按时间正序）。"""
    # 先检查任务是否存在
    task = get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})

    logs = get_task_logs(session, task_id, limit=limit)
    return ok(serialize_models(logs))
