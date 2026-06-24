"""角色 API 路由。"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Character
from app.schemas.business import CharacterCreate, CharacterUpdate
from app.schemas.common import ok
from app.services import business_service

class BatchDeleteRequest(BaseModel):
    ids: list[str]


router = APIRouter(prefix="/projects/{project_id}/characters", tags=["characters"])


@router.get("")
async def api_list_characters(
    project_id: str,
    char_type: Optional[str] = Query(default=None, pattern="^(protagonist|supporting|extra)$"),
    session: Session = Depends(get_session),
):
    """角色列表。"""
    stmt = select(Character).where(Character.project_id == project_id)
    if char_type:
        stmt = stmt.where(Character.char_type == char_type)
    stmt = stmt.order_by(Character.sort_order)
    items = list(session.exec(stmt).all())
    return ok(serialize_models(items))


@router.post("")
async def api_create_character(
    project_id: str,
    payload: CharacterCreate,
    session: Session = Depends(get_session),
):
    """新建角色。"""
    char = business_service.create_entity(session, Character, project_id, payload.model_dump())
    return ok(serialize_model(char), message="角色已创建")


@router.post("/batch-delete")
async def api_batch_delete_characters(
    project_id: str,
    payload: BatchDeleteRequest,
    session: Session = Depends(get_session),
):
    """批量删除角色。"""
    deleted = 0
    errors = []
    for cid in payload.ids:
        char = business_service.get_one(session, Character, cid)
        if char and char.project_id == project_id:
            success = business_service.delete_entity(session, Character, cid)
            if success:
                deleted += 1
            else:
                errors.append({"id": cid, "error": "删除失败"})
        else:
            errors.append({"id": cid, "error": "角色不存在"})
    return ok({"deleted": deleted, "errors": errors}, message=f"已删除 {deleted} 个角色")


@router.get("/{character_id}")
async def api_get_character(
    project_id: str,
    character_id: str,
    session: Session = Depends(get_session),
):
    """角色详情。"""
    char = business_service.get_one(session, Character, character_id)
    if not char or char.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "角色不存在"})
    return ok(serialize_model(char))


@router.patch("/{character_id}")
async def api_update_character(
    project_id: str,
    character_id: str,
    payload: CharacterUpdate,
    session: Session = Depends(get_session),
):
    """更新角色。"""
    char = business_service.get_one(session, Character, character_id)
    if not char or char.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "角色不存在"})
    char = business_service.update_entity(session, Character, character_id, payload.model_dump(exclude_unset=True))
    return ok(serialize_model(char), message="角色已更新")


@router.delete("/{character_id}")
async def api_delete_character(
    project_id: str,
    character_id: str,
    session: Session = Depends(get_session),
):
    """删除角色。"""
    char = business_service.get_one(session, Character, character_id)
    if not char or char.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "角色不存在"})
    success = business_service.delete_entity(session, Character, character_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "角色不存在"})
    return ok(None, message="角色已删除")
