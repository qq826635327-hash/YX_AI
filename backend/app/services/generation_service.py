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
            "size": getattr(payload, "size", None),
            "count": getattr(payload, "count", 1),
            "reference_asset_ids": getattr(payload, "reference_asset_ids", []),
            "reference_preset": getattr(payload, "reference_preset", "full"),
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
    auto_commit: bool = True,
) -> Optional[GenerationTask]:
    """更新任务状态。

    Args:
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

    if status == "running" and not task.started_at:
        task.started_at = datetime.now(timezone.utc)
    if status in ("succeeded", "failed", "cancelled"):
        task.finished_at = datetime.now(timezone.utc)

    session.add(task)
    if auto_commit:
        session.commit()
        session.refresh(task)
    return task


def retry_task(
    session: Session,
    task_id: str,
    provider_id: Optional[str] = None,
    workflow_mapping_id: Optional[str] = None,
) -> Optional[GenerationTask]:
    """重试任务：复制原任务参数，新建一个 pending 任务。"""
    original = session.get(GenerationTask, task_id)
    if not original:
        return None

    new_task = GenerationTask(
        project_id=original.project_id,
        target_type=original.target_type,
        target_id=original.target_id,
        provider_type=original.provider_type,
        provider_id=provider_id or original.provider_id,
        workflow_mapping_id=workflow_mapping_id or original.workflow_mapping_id,
        input_payload=original.input_payload,
        status="pending",
        progress=0,
        retry_count=original.retry_count + 1,
    )
    session.add(new_task)
    session.commit()
    session.refresh(new_task)
    return new_task


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
                "size": payload.size,
                "count": payload.count,
                "reference_asset_ids": payload.reference_asset_ids,
                "reference_preset": getattr(payload, "reference_preset", "full"),
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
    - 对所有 `status='running'` 且 `started_at < 30 秒前` 的任务：
      标记为 `failed`，error="服务重启时任务被中断"
    - 推 WS `task.failed` 让前端立即刷新

    Returns:
        int: 处理的孤儿任务数
    """
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
        logger.warning(f"发现 {len(orphans)} 个孤儿任务，标记为 failed")
        for task in orphans:
            task.status = "failed"
            task.error_message = "服务重启时任务被中断，请重新提交"
            task.finished_at = datetime.now(timezone.utc)
        session.commit()
        # 推 WS 通知（startup 阶段 loop 已运行）
        try:
            from app.ws.routes import push_task_failed
            for task in orphans:
                asyncio.ensure_future(push_task_failed(task.id, "服务重启时任务被中断"))
        except Exception as e:
            logger.warning(f"孤儿任务 WS 推送失败: {e}")
    return len(orphans)
