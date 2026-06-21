"""生成任务提交 API 路由。"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.db import get_session
from app.schemas.common import err, ok
from app.schemas.generation import BatchGenerateRequest, GenerateRequest, GenerateRetryRequest
from app.services.generation_service import (
    cancel_task,
    create_batch_tasks,
    create_task,
    get_task,
    retry_task,
    update_task_status,
)
from app.tasks.execute_task import execute_task_async
from app.ws.routes import push_task_created

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/generate", tags=["generate"])

# 保存后台任务引用，防止被 GC 回收
_background_tasks: set = set()

# 并发执行信号量：限制同时运行的后台任务数量，避免批量提交时压垮系统
_MAX_CONCURRENT_TASKS = 4
_task_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """延迟初始化信号量（需要 event loop 已运行）。"""
    global _task_semaphore
    if _task_semaphore is None:
        _task_semaphore = asyncio.Semaphore(_MAX_CONCURRENT_TASKS)
    return _task_semaphore


async def _run_with_limit(coro):
    """通过信号量限制并发，包装后台任务。"""
    sem = _get_semaphore()
    async with sem:
        return await coro


def _spawn_task(coro):
    """启动后台任务并保存引用，完成后自动移除。"""
    t = asyncio.create_task(_run_with_limit(coro))
    _background_tasks.add(t)
    t.add_done_callback(_background_tasks.discard)
    return t


def _notify_task_created(task_id: str, project_id: str) -> None:
    """WebSocket 通知任务创建（失败时记日志，不阻塞主流程）。"""
    try:
        asyncio.ensure_future(push_task_created(task_id, project_id))
    except Exception as e:
        logger.warning(f"WS 推送 task_created 失败 (task_id={task_id}): {e}")


@router.post("")
async def api_generate(
    payload: GenerateRequest,
    session: Session = Depends(get_session),
):
    """提交生成任务。

    MVP 阶段：创建任务记录，立即更新为 running，然后启动后台执行。
    """
    task = create_task(session, payload)

    # 立即更新为 running（让前端能立即看到）
    update_task_status(session, task.id, status="running", progress=5)

    # 使用 _spawn_task 真正异步执行（不阻塞响应，保存引用防 GC）
    _spawn_task(execute_task_async(task.id))

    # WebSocket 通知
    _notify_task_created(task.id, task.project_id)

    return ok({"task_id": task.id, "status": "running"}, message="任务已提交")


@router.post("/batch")
async def api_generate_batch(
    payload: BatchGenerateRequest,
    session: Session = Depends(get_session),
):
    """批量提交生成任务。

    使用 asyncio.gather 并发启动，避免 BackgroundTasks 的串行阻塞。
    """
    tasks = create_batch_tasks(session, payload)

    # 全部标记为 running（单次 commit，避免 N+1）
    for task in tasks:
        update_task_status(session, task.id, status="running", progress=5, auto_commit=False)
    session.commit()

    for task in tasks:
        _spawn_task(execute_task_async(task.id))

    # WebSocket 通知
    for task in tasks:
        _notify_task_created(task.id, task.project_id)

    return ok(
        {
            "task_ids": [t.id for t in tasks],
            "count": len(tasks),
        },
        message=f"已提交 {len(tasks)} 个生成任务",
    )


@router.post("/{task_id}/retry")
async def api_retry_task(
    task_id: str,
    payload: GenerateRetryRequest,
    session: Session = Depends(get_session),
):
    """重试任务（立即返回，后台异步执行）。"""
    original = get_task(session, task_id)
    if not original:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})

    new_task = retry_task(
        session,
        task_id,
        provider_id=payload.provider_id,
        workflow_mapping_id=payload.workflow_mapping_id,
    )
    if not new_task:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "原任务不存在"})

    # 立即更新为 running，让前端能立即看到
    update_task_status(session, new_task.id, status="running", progress=5)

    # 使用 _spawn_task 真正异步执行（不阻塞响应，保存引用防 GC）
    _spawn_task(execute_task_async(new_task.id))

    # WebSocket 通知
    _notify_task_created(new_task.id, new_task.project_id)

    return ok({"task_id": new_task.id, "status": "running"}, message="任务已重新提交")


@router.post("/{task_id}/cancel")
async def api_cancel_task(task_id: str, session: Session = Depends(get_session)):
    """取消任务。"""
    task = cancel_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})
    return ok({"task_id": task.id, "status": task.status}, message="任务已取消")
