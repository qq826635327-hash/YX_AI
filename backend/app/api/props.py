"""道具 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Prop
from app.schemas.business import PropCreate, PropUpdate
from app.schemas.common import ok
from app.services import business_service

router = APIRouter(prefix="/projects/{project_id}/props", tags=["props"])


@router.get("")
async def api_list_props(project_id: str, session: Session = Depends(get_session)):
    items = business_service.list_by_project(session, Prop, project_id)
    return ok(serialize_models(items))


@router.post("")
async def api_create_prop(
    project_id: str,
    payload: PropCreate,
    session: Session = Depends(get_session),
):
    prop = business_service.create_entity(session, Prop, project_id, payload.model_dump())
    return ok(serialize_model(prop), message="道具已创建")


@router.get("/{prop_id}")
async def api_get_prop(project_id: str, prop_id: str, session: Session = Depends(get_session)):
    prop = business_service.get_one(session, Prop, prop_id)
    if not prop or prop.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "道具不存在"})
    return ok(serialize_model(prop))


@router.patch("/{prop_id}")
async def api_update_prop(
    project_id: str,
    prop_id: str,
    payload: PropUpdate,
    session: Session = Depends(get_session),
):
    prop = business_service.get_one(session, Prop, prop_id)
    if not prop or prop.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "道具不存在"})
    prop = business_service.update_entity(session, Prop, prop_id, payload.model_dump(exclude_unset=True))
    return ok(serialize_model(prop), message="道具已更新")


@router.delete("/{prop_id}")
async def api_delete_prop(project_id: str, prop_id: str, session: Session = Depends(get_session)):
    prop = business_service.get_one(session, Prop, prop_id)
    if not prop or prop.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "道具不存在"})
    success = business_service.delete_entity(session, Prop, prop_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "道具不存在"})
    return ok(None, message="道具已删除")
