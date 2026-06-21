"""API Provider 配置路由。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlmodel import Session

from app.db import get_session
from app.providers import get_handler_class, list_registered
from app.schemas.common import err, ok
from app.schemas.generation import ProviderCapabilitiesView, ProviderCreate, ProviderUpdate

logger = logging.getLogger(__name__)
from app.services.config_service import (
    create_provider,
    delete_provider,
    get_provider,
    list_providers,
    provider_to_view,
    update_provider,
)

router = APIRouter(prefix="/config/providers", tags=["config"])


@router.get("")
async def api_list_providers(
    enabled: Optional[bool] = Query(default=None),
    session: Session = Depends(get_session),
):
    """Provider 列表（脱敏）。"""
    items = list_providers(session, enabled=enabled)
    return ok([provider_to_view(p) for p in items])


@router.post("")
async def api_create_provider(
    payload: ProviderCreate,
    session: Session = Depends(get_session),
):
    """新增 Provider。"""
    provider = create_provider(session, payload)
    return ok(provider_to_view(provider), message="Provider 已创建")


@router.get("/comfyui/capabilities")
async def api_get_comfyui_capabilities():
    """获取 ComfyUI 本地工作流的能力声明。"""
    return ok({
        "provider_kind": "comfyui",
        "param_specs": [],  # ComfyUI 的参数由工作流映射定义
        "batch_support": False,
        "max_count": 1,
        "reference_image": True,
        "extra_fields": [
            {"key": "workflow_mapping_id", "label": "工作流映射", "type": "workflow_select"},
        ],
    })


@router.get("/{provider_id}")
async def api_get_provider(provider_id: str, session: Session = Depends(get_session)):
    provider = get_provider(session, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Provider 不存在"})
    return ok(provider_to_view(provider))


@router.patch("/{provider_id}")
async def api_update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    session: Session = Depends(get_session),
):
    provider = update_provider(session, provider_id, payload)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Provider 不存在"})
    return ok(provider_to_view(provider), message="Provider 已更新")


@router.delete("/{provider_id}")
async def api_delete_provider(provider_id: str, session: Session = Depends(get_session)):
    success = delete_provider(session, provider_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Provider 不存在"})
    return ok(None, message="Provider 已删除")


@router.post("/{provider_id}/test")
async def api_test_provider(
    provider_id: str,
    session: Session = Depends(get_session),
):
    """测试 Provider 连接。"""
    provider = get_provider(session, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Provider 不存在"})

    # 如果有对应的 Handler，调用 Handler 的测试方法（如果有）
    handler_cls = get_handler_class(provider.provider_kind)
    if handler_cls:
        # TODO: 实现 Handler 的 test_connection() 方法
        test_result = {
            "provider_kind": provider.provider_kind,
            "handler": handler_cls.__name__,
            "test_status": "handler_found",
            "message": f"找到 Handler: {handler_cls.__name__}",
        }
    else:
        test_result = {
            "provider_kind": provider.provider_kind,
            "test_status": "no_handler",
            "message": f"未找到 Handler（provider_kind={provider.provider_kind}）",
        }

    return ok(test_result)


@router.get("/{provider_id}/capabilities")
async def api_get_provider_capabilities(
    provider_id: str,
    model: Optional[str] = Query(default=None, description="指定模型名，获取该模型对应的能力声明"),
    session: Session = Depends(get_session),
):
    """获取 Provider 下指定模型的能力声明（含动态参数规范）。

    优先从 Provider Handler 获取（如果已注册），
    否则返回空 capabilities（前端会禁用生成按钮）。
    """
    provider = get_provider(session, provider_id)
    if not provider:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Provider 不存在"})

    # 取 Provider 的代表模型：优先用传入的 model 参数，其次第一个模型，最后兼容旧 model 字段
    available_models = sorted(provider.models or [], key=lambda x: x.sort_order)
    selected_model = None
    if model:
        selected_model = next((m.model_name for m in available_models if m.model_name == model), None)
    if not selected_model:
        selected_model = available_models[0].model_name if available_models else (provider.model or None)

    # 从注册表获取 Handler，传入 model 名获取对应 param_specs
    logger.debug(f"[capabilities] 开始查找 Handler: provider_kind={provider.provider_kind}")
    handler_cls = get_handler_class(provider.provider_kind)
    logger.debug(f"[capabilities] get_handler_class() 返回: {handler_cls}")

    model_views = [
        {"id": m.id, "model_name": m.model_name, "tags": m.tags or [], "sort_order": m.sort_order}
        for m in available_models
    ]

    if not handler_cls:
        # 未找到 Handler，返回空 capabilities
        logger.warning(f"[capabilities] 未找到 Handler: provider_kind={provider.provider_kind}，已注册的 Handler: {list_registered()}")
        return ok({
            "provider_kind": provider.provider_kind,
            "model": selected_model,
            "models": model_views,
            "param_specs": [],
            "batch_support": False,
            "max_count": 1,
            "reference_image": False,
        })

    # 调用 Handler 的 get_capabilities() 类方法
    logger.debug(f"[capabilities] handler_cls={handler_cls.__name__}, model={selected_model}")
    capabilities = handler_cls.get_capabilities(model=selected_model)
    capabilities.setdefault("model", selected_model)
    capabilities.setdefault("models", model_views)
    logger.debug(f"[capabilities] 返回值: {capabilities}")
    return ok(capabilities)
