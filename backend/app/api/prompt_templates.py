"""提示词模板 API 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.schemas.common import ok
from app.schemas.prompt_template import (
    PromptTemplateCreate,
    PromptTemplateUpdate,
)
from app.services import prompt_template_service

router = APIRouter(prefix="/prompt-templates", tags=["提示词模板"])


@router.get("")
async def list_prompt_templates(
    template_type: Optional[str] = Query(None, description="按模板类型筛选"),
    session: Session = Depends(get_session),
):
    """获取提示词模板列表。"""
    items = prompt_template_service.list_templates(session, template_type=template_type)
    return ok(serialize_models(items))


@router.get("/{template_id}")
async def get_prompt_template(
    template_id: str,
    session: Session = Depends(get_session),
):
    """获取单个模板详情。"""
    item = prompt_template_service.get_template(session, template_id)
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ok(serialize_model(item))


@router.post("", status_code=201)
async def create_prompt_template(
    data: PromptTemplateCreate,
    session: Session = Depends(get_session),
):
    """创建提示词模板。"""
    try:
        item = prompt_template_service.create_template(session, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok(serialize_model(item), message="模板已创建")


@router.put("/{template_id}")
async def update_prompt_template(
    template_id: str,
    data: PromptTemplateUpdate,
    session: Session = Depends(get_session),
):
    """更新提示词模板。"""
    try:
        item = prompt_template_service.update_template(session, template_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not item:
        raise HTTPException(status_code=404, detail="模板不存在")
    return ok(serialize_model(item), message="模板已更新")


@router.delete("/{template_id}")
async def delete_prompt_template(
    template_id: str,
    session: Session = Depends(get_session),
):
    """删除提示词模板。内置模板不可删除。"""
    deleted = prompt_template_service.delete_template(session, template_id)
    if not deleted:
        raise HTTPException(status_code=400, detail="模板不存在或为内置模板，无法删除")
    return ok(None, message="模板已删除")
