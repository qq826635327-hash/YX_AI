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
# 实际并发数从配置读取，延迟初始化
_task_semaphore: asyncio.Semaphore | None = None


def _get_max_concurrent() -> int:
    """从配置读取最大并发数。"""
    from app.core.config import get_settings
    return get_settings().tasks.max_concurrent


def _get_semaphore() -> asyncio.Semaphore:
    """延迟初始化信号量（需要 event loop 已运行）。"""
    global _task_semaphore
    if _task_semaphore is None:
        _task_semaphore = asyncio.Semaphore(_get_max_concurrent())
    return _task_semaphore


def reset_task_state() -> None:
    """重置任务状态（应用重启时调用，处理 --reload 模式下 event loop 重建的情况）。"""
    global _task_semaphore
    _task_semaphore = None
    _background_tasks.clear()


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


async def drain_tasks(timeout: float = 120.0) -> None:
    """优雅关闭：等待运行中的任务完成，超时则取消。

    在 main.py lifespan 的 shutdown 阶段调用。
    - 默认等待 120 秒（视频任务可能需要几分钟完成轮询）
    - 超时后强制取消剩余任务（execute_task 的 CancelledError 分支会标记为 cancelled）
    - 下次启动时 recover_orphan_tasks 兜底处理漏网之鱼
    """
    if not _background_tasks:
        return

    pending = list(_background_tasks)
    logger.info(f"正在等待 {len(pending)} 个后台任务完成（超时 {timeout}s）...")

    done, still_running = await asyncio.wait(
        pending, timeout=timeout, return_when=asyncio.ALL_COMPLETED
    )

    for t in still_running:
        t.cancel()

    if still_running:
        # 给取消的任务一个机会执行 finally/cancelled 清理
        await asyncio.wait(still_running, timeout=5.0)
        logger.warning(f"关闭时 {len(still_running)} 个任务未完成，已强制取消")
    else:
        logger.info(f"所有 {len(pending)} 个后台任务已正常完成")


def has_running_tasks() -> bool:
    """检查是否有正在运行的后台任务。"""
    return bool(_background_tasks)


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
    """重试任务：重置本条任务状态并重新执行（不新建任务）。"""
    original = get_task(session, task_id)
    if not original:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})

    # 如果原任务还在运行中，先取消旧协程，避免并发写同一行
    if original.status == "running":
        from app.tasks.execute_task import request_task_cancel
        request_task_cancel(task_id)
        # 给旧协程一点时间退出
        import asyncio
        await asyncio.sleep(0.1)

    retried = retry_task(
        session,
        task_id,
        provider_id=payload.provider_id,
        workflow_mapping_id=payload.workflow_mapping_id,
    )
    if not retried:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "原任务不存在"})

    # 立即更新为 running，让前端能立即看到
    update_task_status(session, retried.id, status="running", progress=5)

    # 使用 _spawn_task 真正异步执行（不阻塞响应，保存引用防 GC）
    _spawn_task(execute_task_async(retried.id))

    # WebSocket 通知
    _notify_task_created(retried.id, retried.project_id)

    return ok({"task_id": retried.id, "status": "running"}, message="任务已重新执行")


@router.post("/{task_id}/cancel")
async def api_cancel_task(task_id: str, session: Session = Depends(get_session)):
    """取消任务。"""
    task = cancel_task(session, task_id)
    if not task:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "任务不存在"})
    return ok({"task_id": task.id, "status": task.status}, message="任务已取消")
