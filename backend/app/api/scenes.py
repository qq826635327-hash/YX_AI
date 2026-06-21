"""场景 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Scene
from app.schemas.business import SceneCreate, SceneUpdate
from app.schemas.common import ok
from app.services import business_service

router = APIRouter(prefix="/projects/{project_id}/scenes", tags=["scenes"])


@router.get("")
async def api_list_scenes(project_id: str, session: Session = Depends(get_session)):
    items = business_service.list_by_project(session, Scene, project_id)
    return ok(serialize_models(items))


@router.post("")
async def api_create_scene(
    project_id: str,
    payload: SceneCreate,
    session: Session = Depends(get_session),
):
    scene = business_service.create_entity(session, Scene, project_id, payload.model_dump())
    return ok(serialize_model(scene), message="场景已创建")


@router.get("/{scene_id}")
async def api_get_scene(project_id: str, scene_id: str, session: Session = Depends(get_session)):
    scene = business_service.get_one(session, Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "场景不存在"})
    return ok(serialize_model(scene))


@router.patch("/{scene_id}")
async def api_update_scene(
    project_id: str,
    scene_id: str,
    payload: SceneUpdate,
    session: Session = Depends(get_session),
):
    scene = business_service.get_one(session, Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "场景不存在"})
    scene = business_service.update_entity(session, Scene, scene_id, payload.model_dump(exclude_unset=True))
    return ok(serialize_model(scene), message="场景已更新")


@router.delete("/{scene_id}")
async def api_delete_scene(project_id: str, scene_id: str, session: Session = Depends(get_session)):
    scene = business_service.get_one(session, Scene, scene_id)
    if not scene or scene.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "场景不存在"})
    success = business_service.delete_entity(session, Scene, scene_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "场景不存在"})
    return ok(None, message="场景已删除")
