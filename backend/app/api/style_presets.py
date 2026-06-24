"""画风预置 API 路由。"""

from __future__ import annotations

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.schemas.common import ok
from app.schemas.style_preset import StylePresetCreate, StylePresetUpdate
from app.services import style_preset_service

router = APIRouter(prefix="/style-presets", tags=["画风预置"])


class ReorderRequest(BaseModel):
    """批量排序请求。"""
    ordered_ids: List[str]


@router.get("")
async def list_style_presets(session: Session = Depends(get_session)):
    """获取所有画风预置。"""
    items = style_preset_service.list_presets(session)
    return ok(serialize_models(items))


@router.post("", status_code=201)
async def create_style_preset(
    data: StylePresetCreate,
    session: Session = Depends(get_session),
):
    """创建画风预置。"""
    try:
        item = style_preset_service.create_preset(session, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return ok(serialize_model(item), message="画风预置已创建")


@router.put("/reorder")
async def reorder_style_presets(
    data: ReorderRequest,
    session: Session = Depends(get_session),
):
    """批量排序画风预置。"""
    style_preset_service.reorder_presets(session, data.ordered_ids)
    items = style_preset_service.list_presets(session)
    return ok(serialize_models(items), message="排序已更新")


@router.get("/{preset_id}")
async def get_style_preset(preset_id: str, session: Session = Depends(get_session)):
    """获取单个画风预置。"""
    item = style_preset_service.get_preset(session, preset_id)
    if not item:
        raise HTTPException(status_code=404, detail="画风预置不存在")
    return ok(serialize_model(item))


@router.put("/{preset_id}")
async def update_style_preset(
    preset_id: str,
    data: StylePresetUpdate,
    session: Session = Depends(get_session),
):
    """更新画风预置。"""
    try:
        item = style_preset_service.update_preset(session, preset_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not item:
        raise HTTPException(status_code=404, detail="画风预置不存在")
    return ok(serialize_model(item), message="画风预置已更新")


@router.delete("/{preset_id}")
async def delete_style_preset(
    preset_id: str,
    session: Session = Depends(get_session),
):
    """删除画风预置。"""
    deleted = style_preset_service.delete_preset(session, preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="画风预置不存在")
    return ok(None, message="画风预置已删除")
