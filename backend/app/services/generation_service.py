# -*- coding: utf-8 -*-
"""生成任务服务。"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Union

from sqlalchemy import delete, func, update
from sqlmodel import Session, select

from app.db import session_scope
from app.models import GenerationTask
from app.schemas.generation import GenerateRequest

logger = logging.getLogger(__name__)


def create_task(session: Session, payload: GenerateRequest) -> GenerationTask:
    """创建生成任务（pending 状态）。"""
    task = GenerationTask(
        project_id=payload.project_id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        provider_type=payload.provider_type,
        provider_id=payload.provider_id,
        workflow_mapping_id=payload.workflow_mapping_id,
        input_payload={
            "prompt": payload.prompt,
            "model": getattr(payload, "model", None),
            "size": getattr(payload, "size", None),
            "count": getattr(payload, "count", 1),
            "reference_asset_ids": getattr(payload, "reference_asset_ids", []),
            "extra_params": payload.extra_params,
        },
        status="pending",
        progress=0,
    )
    session.add(task)
    session.commit()
    session.refresh(task)
    return task


def get_task(session: Session, task_id: str) -> Optional[GenerationTask]:
    return session.get(GenerationTask, task_id)


def list_tasks(
    session: Session,
    project_id: Optional[str] = None,
    status: Optional[Union[str, List[str]]] = None,  # 支持单个状态或状态列表
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[GenerationTask], int]:
    """任务列表（支持多状态过滤）。"""
    stmt = select(GenerationTask)
    if project_id:
        stmt = stmt.where(GenerationTask.project_id == project_id)

    # 支持多状态过滤
    if status:
        if isinstance(status, list):
            stmt = stmt.where(GenerationTask.status.in_(status))
        else:
            stmt = stmt.where(GenerationTask.status == status)

    if target_type:
        stmt = stmt.where(GenerationTask.target_type == target_type)
    if target_id:
        stmt = stmt.where(GenerationTask.target_id == target_id)

    # 使用 SQL COUNT 而非全量加载后 len()
    # 复用 stmt 的 where 条件，避免重复构建
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.exec(count_stmt).one()

    offset = (page - 1) * page_size
    stmt = stmt.order_by(GenerationTask.created_at.desc()).offset(offset).limit(page_size)
    items = list(session.exec(stmt).all())
    return items, total


def clear_tasks(
    session: Session,
    project_id: Optional[str] = None,
    status: Optional[Union[str, List[str]]] = None,
) -> int:
    """批量清理已结束任务。

    默认清理 succeeded / failed / cancelled 这类已结束状态；
    可通过 status 指定其他状态列表。不传 status 时只删已结束任务，避免误删 running。

    清理时会：
    1. 删除关联的 task_logs 记录
    2. 把 assets 的 task_id 置为 NULL（保留已生成的素材文件）
    3. 删除 generation_tasks 记录
    """
    if status is None:
        status = ["succeeded", "failed", "cancelled"]
    status_list = [status] if isinstance(status, str) else list(status)

    stmt = select(GenerationTask).where(GenerationTask.status.in_(status_list))
    if project_id:
        stmt = stmt.where(GenerationTask.project_id == project_id)

    items = list(session.exec(stmt).all())
    task_ids = [t.id for t in items]
    if not task_ids:
        return 0

    # 1. 删除任务日志
    from app.models import TaskLog
    session.exec(
        delete(TaskLog).where(TaskLog.task_id.in_(task_ids))  # type: ignore[arg-type]
    )

    # 2. 解绑素材（保留文件）
    from app.models import Asset
    session.exec(
        update(Asset)
        .where(Asset.task_id.in_(task_ids))  # type: ignore[arg-type]
        .values(task_id=None)
    )

    # 3. 批量删除任务（避免 N+1 逐条 delete）
    count = len(items)
    session.exec(
        delete(GenerationTask).where(GenerationTask.id.in_(task_ids))  # type: ignore[arg-type]
    )
    session.commit()
    logger.info(f"清理了 {count} 个任务 (project_id={project_id}, status={status_list})")
    return count


def update_task_status(
    session: Session,
    task_id: str,
    status: str,
    progress: Optional[int] = None,
    error: Optional[str] = None,
    output_asset_id: Optional[str] = None,
    output_payload: Optional[dict] = None,
    auto_commit: bool = True,
) -> Optional[GenerationTask]:
    """更新任务状态。

    Args:
        output_payload: 生成结果元数据（usage、duration_ms、provider、model 等），
                        仅任务成功时写入，用于成本追踪。
        auto_commit: 是否自动提交。批量操作时设为 False，由调用方统一 commit。
    """
    task = session.get(GenerationTask, task_id)
    if not task:
        return None

    task.status = status
    if progress is not None:
        task.progress = progress
    if error is not None:
        task.error_message = error
    elif status == "succeeded":
        # 成功时清空之前的错误信息
        task.error_message = None
    if output_asset_id is not None:
        task.output_asset_id = output_asset_id
    if output_payload is not None:
        task.output_payload = output_payload

    if status == "running" and not task.started_at:
        task.started_at = datetime.now(timezone.utc)
    if status in ("succeeded", "failed", "cancelled"):
        task.finished_at = datetime.now(timezone.utc)

    session.add(task)
    if auto_commit:
        # busy_timeout=30000 已在引擎层设置，SQLite 会自动等待锁释放。
        # 不在同步函数里做 sleep 重试，避免在 async 调用栈中阻塞事件循环。
        session.commit()
        session.refresh(task)
    return task


def retry_task(
    session: Session,
    task_id: str,
    provider_id: Optional[str] = None,
    workflow_mapping_id: Optional[str] = None,
) -> Optional[GenerationTask]:
    """重试任务：重置本条任务状态为 pending，不新建任务。

    重置内容：
    - status → pending（由调用方立即改为 running）
    - progress → 0
    - error_message → 清空
    - output_asset_id → 清空
    - output_payload → 清空
    - started_at / finished_at → 清空
    - retry_count → +1
    - provider_id / workflow_mapping_id → 可选覆盖
    """
    original = session.get(GenerationTask, task_id)
    if not original:
        return None

    # 取消可能正在等待的自动重试协程
    from app.tasks.execute_task import cancel_auto_retry
    cancel_auto_retry(task_id)

    original.status = "pending"
    original.progress = 0
    original.error_message = None
    original.output_asset_id = None
    original.output_payload = None
    original.started_at = None
    original.finished_at = None
    original.retry_count += 1
    original.auto_retry_count = 0  # 手动重试重置自动重试计数

    # 允许重试时切换 Provider/工作流
    if provider_id is not None:
        original.provider_id = provider_id
    if workflow_mapping_id is not None:
        original.workflow_mapping_id = workflow_mapping_id

    # 手动重试时始终清除断点续传数据，确保重新调用 API 而非复用旧 URL
    if original.input_payload:
        original.input_payload.pop("_video_task_id", None)
        original.input_payload.pop("_result_urls", None)

    session.add(original)
    session.commit()
    session.refresh(original)
    return original


def cancel_task(session: Session, task_id: str) -> Optional[GenerationTask]:
    """取消任务。

    除了在 DB 中标记为 cancelled，还向执行器发送内存中的取消信号，
    使正在运行的任务能够尽早退出，而不是继续生成图片。
    """
    from app.tasks.execute_task import request_task_cancel

    request_task_cancel(task_id)
    return update_task_status(session, task_id, status="cancelled")


def create_batch_tasks(session: Session, payload) -> list[GenerationTask]:
    """批量创建生成任务。"""
    tasks = []
    for target in payload.targets:
        task = GenerationTask(
            project_id=payload.project_id,
            target_type=target.target_type,
            target_id=target.target_id,
            provider_type=payload.provider_type,
            provider_id=payload.provider_id,
            workflow_mapping_id=payload.workflow_mapping_id,
            input_payload={
                "prompt": target.prompt,
                "model": getattr(payload, "model", None),
                "size": payload.size,
                "count": payload.count,
                "reference_asset_ids": payload.reference_asset_ids,
                "extra_params": payload.extra_params,
            },
            status="pending",
            progress=0,
        )
        session.add(task)
        tasks.append(task)
    session.commit()
    for task in tasks:
        session.refresh(task)
    return tasks


def recover_orphan_tasks() -> int:
    """恢复被中断的任务。

    场景：uvicorn 重启 / 进程崩溃会导致 `running` 状态的任务永远卡住
    （`asyncio.create_task` 创建的协程在进程退出时被杀掉，但 DB 没机会更新状态）。
    这种"孤儿任务"在用户视角看就是"图片正在生成中但永远不会完成"。

    处理：
    - 有 _result_urls（API 已成功）的孤儿任务：重置为 pending，自动重试下载
    - 无 _result_urls 的孤儿任务：标记为 failed，error="服务重启时任务被中断"
    - 推 WS `task.failed` 让前端立即刷新

    Returns:
        int: 处理的孤儿任务数
    """
    from app.core.config import get_settings

    threshold = datetime.now(timezone.utc) - timedelta(seconds=30)
    with session_scope() as session:
        orphans = session.exec(
            select(GenerationTask).where(
                GenerationTask.status == "running",
                GenerationTask.started_at < threshold,
            )
        ).all()
        if not orphans:
            logger.info("没有需要恢复的孤儿任务")
            return 0

        settings = get_settings()
        auto_retry_tasks = []
        failed_tasks = []

        for task in orphans:
            result_urls = (task.input_payload or {}).get("_result_urls")
            video_task_id = (task.input_payload or {}).get("_video_task_id")
            # SQLite 读回的 datetime 可能丢失 tzinfo（naive），与 aware UTC 相减会 TypeError
            created_at = task.created_at
            if created_at is None:
                age_minutes = 0.0
            else:
                if created_at.tzinfo is None:
                    created_at = created_at.replace(tzinfo=timezone.utc)
                age_minutes = (datetime.now(timezone.utc) - created_at).total_seconds() / 60
            # 有 _result_urls 或 _video_task_id 且未超时的任务，自动重试下载/轮询
            if ((result_urls or video_task_id)
                    and task.auto_retry_count < settings.tasks.auto_retry_max_attempts
                    and age_minutes < settings.tasks.task_max_age_minutes):
                task.status = "pending"
                task.progress = 0
                task.auto_retry_count += 1
                task.error_message = f"服务重启，自动重试下载（第{task.auto_retry_count}次）"
                task.started_at = None
                task.finished_at = None
                auto_retry_tasks.append(task)
            else:
                task.status = "failed"
                task.error_message = "服务重启时任务被中断，请重新提交"
                task.finished_at = datetime.now(timezone.utc)
                failed_tasks.append(task)

        session.commit()

        if auto_retry_tasks:
            logger.info(f"发现 {len(auto_retry_tasks)} 个有 API 结果的孤儿任务，将自动重试下载")
        if failed_tasks:
            logger.warning(f"发现 {len(failed_tasks)} 个孤儿任务，标记为 failed")

        # 推 WS 通知 + 自动重试
        try:
            from app.ws.routes import push_task_failed
            for task in failed_tasks:
                asyncio.ensure_future(push_task_failed(task.id, "服务重启时任务被中断"))
            for task in auto_retry_tasks:
                asyncio.ensure_future(push_task_failed(task.id, task.error_message or "服务重启，自动重试下载"))
        except Exception as e:
            logger.warning(f"孤儿任务 WS 推送失败: {e}")

        # 延迟后自动重试有 _result_urls 的任务
        if auto_retry_tasks:
            async def _retry_orphans():
                await asyncio.sleep(2)  # 等服务完全启动
                from app.api.generate import _spawn_task
                from app.tasks.execute_task import execute_task_async
                for task in auto_retry_tasks:
                    _spawn_task(execute_task_async(task.id))
                    logger.info(f"孤儿任务 {task.id} 开始自动重试下载")
            asyncio.ensure_future(_retry_orphans())

    # 清理内存中残留的取消事件和自动重试协程（进程重启后这些内存状态已失效）
    try:
        from app.tasks.execute_task import _task_cancel_events, _auto_retry_tasks
        _task_cancel_events.clear()
        # 取消残留的自动重试协程
        for t in list(_auto_retry_tasks.values()):
            if not t.done():
                t.cancel()
        _auto_retry_tasks.clear()
        if orphans:
            logger.info("已清理内存中残留的任务取消事件和自动重试协程")
    except Exception as e:
        logger.debug(f"清理内存字典失败（可忽略）: {e}")

    return len(orphans)
