"""系统配置中心 API 路由（ComfyUI 配置、系统信息、默认模型等）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session

from app.core.config import encrypt_secret, get_settings, save_settings_to_yaml
from app.db import get_session
from app.schemas.common import ok

router = APIRouter(prefix="/config", tags=["config"])


class DefaultModelsUpdate(BaseModel):
    default_image_model: str | None = None
    default_text_model: str | None = None
    default_video_model: str | None = None


class TasksConfigUpdate(BaseModel):
    rate_limit_retry: int | None = None
    rate_limit_wait: int | None = None
    smart_fallback: bool | None = None
    max_concurrent: int | None = None


@router.get("/system")
async def api_system_config(session: Session = Depends(get_session)):
    """系统配置摘要（脱敏，供前端展示状态）。"""
    settings = get_settings()
    return ok({
        "app": {
            "name": settings.app.name,
            "version": settings.app.version,
        },
        "comfyui": {
            "base_url": settings.comfyui.base_url,
            "enabled": settings.comfyui.enabled,
            "timeout": settings.comfyui.timeout,
        },
        "storage": {
            "projects_root": str(settings.projects_root_abs),
        },
        "default_models": {
            "default_image_model": settings.default_models.default_image_model,
            "default_text_model": settings.default_models.default_text_model,
            "default_video_model": settings.default_models.default_video_model,
        },
        "tasks": {
            "rate_limit_retry": settings.tasks.rate_limit_retry,
            "rate_limit_wait": settings.tasks.rate_limit_wait,
            "smart_fallback": settings.tasks.smart_fallback,
            "max_concurrent": settings.tasks.max_concurrent,
        },
    })


@router.patch("/default-models")
async def api_update_default_models(body: DefaultModelsUpdate):
    """运行时更新默认模型配置，并持久化到 config.yaml。"""
    settings = get_settings()
    if body.default_image_model is not None:
        settings.default_models.default_image_model = body.default_image_model
    if body.default_text_model is not None:
        settings.default_models.default_text_model = body.default_text_model
    if body.default_video_model is not None:
        settings.default_models.default_video_model = body.default_video_model
    # 持久化到 config.yaml，防止重启后丢失
    save_settings_to_yaml(settings)
    return ok({
        "default_image_model": settings.default_models.default_image_model,
        "default_text_model": settings.default_models.default_text_model,
        "default_video_model": settings.default_models.default_video_model,
    })


@router.patch("/tasks")
async def api_update_tasks_config(body: TasksConfigUpdate):
    """运行时更新任务配置（速率限制重试、智能降级、并发数），并持久化。"""
    settings = get_settings()

    if body.rate_limit_retry is not None:
        settings.tasks.rate_limit_retry = max(0, body.rate_limit_retry)
    if body.rate_limit_wait is not None:
        settings.tasks.rate_limit_wait = max(10, body.rate_limit_wait)
    if body.smart_fallback is not None:
        settings.tasks.smart_fallback = body.smart_fallback
    if body.max_concurrent is not None:
        new_max = max(1, min(20, body.max_concurrent))
        settings.tasks.max_concurrent = new_max
        # 重置信号量使新并发数生效（下次 _get_semaphore 调用时重建）
        from app.api.generate import reset_task_state
        reset_task_state()

    # 持久化到 config.yaml，防止重启后丢失
    save_settings_to_yaml(settings)

    return ok({
        "rate_limit_retry": settings.tasks.rate_limit_retry,
        "rate_limit_wait": settings.tasks.rate_limit_wait,
        "smart_fallback": settings.tasks.smart_fallback,
        "max_concurrent": settings.tasks.max_concurrent,
    })


@router.get("/comfyui")
async def api_comfyui_config(session: Session = Depends(get_session)):
    """ComfyUI 配置详情。"""
    settings = get_settings()
    return ok({
        "base_url": settings.comfyui.base_url,
        "enabled": settings.comfyui.enabled,
        "timeout": settings.comfyui.timeout,
        "output_dir": settings.comfyui.output_dir,
    })


@router.post("/backup")
async def api_manual_backup():
    """手动触发数据库备份 + WAL checkpoint。

    返回备份文件路径和 checkpoint 结果。
    """
    from app.services.backup_service import backup_database, wal_checkpoint

    backup_path = backup_database()
    checkpoint_ok = wal_checkpoint()

    return ok({
        "backup_file": str(backup_path) if backup_path else None,
        "wal_checkpoint": checkpoint_ok,
    })
