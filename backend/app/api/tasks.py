"""任务中心 API 路由。"""

from __future__ import annotations

import copy
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


def _strip_large_fields(task_dict: dict) -> dict:
    """从任务字典中移除大数据字段，减少列表接口的响应体积。

    主要移除 input_payload.extra_params.reference_images（base64 图片数据，可达数 MB），
    这些数据仅在任务详情接口中返回。
    """
    input_payload = task_dict.get("input_payload")
    if isinstance(input_payload, dict):
        extra_params = input_payload.get("extra_params")
        if isinstance(extra_params, dict) and "reference_images" in extra_params:
            # 浅拷贝避免修改原始对象
            task_dict = copy.copy(task_dict)
            input_payload = copy.copy(input_payload)
            extra_params = copy.copy(extra_params)
            # 只保留 reference_images 的长度信息，不传 base64 数据
            ref_imgs = extra_params["reference_images"]
            if isinstance(ref_imgs, list):
                extra_params["reference_images_count"] = len(ref_imgs)
            del extra_params["reference_images"]
            input_payload["extra_params"] = extra_params
            task_dict["input_payload"] = input_payload
    return task_dict


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
    # 列表接口剥离大数据字段（base64 图片），减少响应体积
    stripped = [_strip_large_fields(t) for t in serialize_models(items)]
    return paginate(stripped, total, page, page_size)


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


@router.get("/queue/status")
async def api_queue_status(session: Session = Depends(get_session)):
    """任务队列状态（可观测性端点）。

    返回：
    - db: 数据库中各状态的任务计数
    - runtime: 内存中的活跃任务数和信号量状态
    """
    from sqlalchemy import func
    from sqlmodel import select

    from app.models import GenerationTask

    # DB 层面：按状态统计
    stmt = (
        select(GenerationTask.status, func.count().label("count"))
        .group_by(GenerationTask.status)
    )
    rows = session.exec(stmt).all()
    db_counts = {row[0]: row[1] for row in rows}

    # 内存层面：活跃 asyncio 任务和信号量
    from app.api.generate import _background_tasks, _task_semaphore, _get_max_concurrent

    max_concurrent = _get_max_concurrent()
    active_in_memory = len(_background_tasks)
    semaphore_available = (
        _task_semaphore._value if _task_semaphore else max_concurrent
    )

    return ok({
        "db": db_counts,
        "runtime": {
            "active_tasks": active_in_memory,
            "semaphore_available": semaphore_available,
            "semaphore_max": max_concurrent,
        },
    })


@router.get("/{task_id}")
async def api_get_task(task_id: str, session: Session = Depends(get_session)):
    """任务详情。"""
    task = get_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})
    # 详情接口也剥离大数据字段，避免 6MB+ 的 base64 参考图拖慢响应
    return ok(_strip_large_fields(serialize_model(task)))


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
