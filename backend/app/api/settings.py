"""系统配置中心 API 路由（ComfyUI 配置、系统信息等）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.config import encrypt_secret, get_settings
from app.db import get_session
from app.schemas.common import ok
from app.schemas.generation import LLMConfigUpdate

router = APIRouter(prefix="/config", tags=["config"])


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
        "llm": {
            "enabled": settings.llm.enabled,
            "provider": settings.llm.provider,
            "model": settings.llm.model,
            "base_url": settings.llm.base_url,
        },
        "storage": {
            "projects_root": str(settings.projects_root_abs),
        },
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


@router.patch("/llm")
async def api_update_llm_config(body: LLMConfigUpdate):
    """运行时更新 LLM 配置（直接修改内存中的 Settings 单例）。"""
    settings = get_settings()

    if body.enabled is not None:
        settings.llm.enabled = body.enabled
    if body.provider is not None:
        settings.llm.provider = body.provider
    if body.base_url is not None:
        settings.llm.base_url = body.base_url
    if body.model is not None:
        settings.llm.model = body.model
    if body.api_key is not None:
        settings.llm.api_key = encrypt_secret(body.api_key)

    return ok({
        "enabled": settings.llm.enabled,
        "provider": settings.llm.provider,
        "model": settings.llm.model,
        "base_url": settings.llm.base_url,
    })
