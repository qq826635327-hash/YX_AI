"""分镜 API 路由。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Episode, Shot
from app.schemas.business import ShotCreate, ShotUpdate
from app.schemas.common import ok
from app.services import business_service

router = APIRouter(tags=["shots"])


@router.get("/episodes/{episode_id}/shots")
async def api_list_shots(episode_id: str, session: Session = Depends(get_session)):
    """按剧集列出分镜。"""
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    items = business_service.list_shots_by_episode(session, episode_id)
    return ok(serialize_models(items))


@router.post("/episodes/{episode_id}/shots")
async def api_create_shot(
    episode_id: str,
    payload: ShotCreate,
    session: Session = Depends(get_session),
):
    """新建分镜。"""
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    shot = business_service.create_shot(session, episode_id, episode.project_id, payload.model_dump())
    return ok(serialize_model(shot), message="分镜已创建")


@router.get("/shots/{shot_id}")
async def api_get_shot(shot_id: str, session: Session = Depends(get_session)):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    return ok(serialize_model(shot))


@router.patch("/shots/{shot_id}")
async def api_update_shot(
    shot_id: str,
    payload: ShotUpdate,
    session: Session = Depends(get_session),
):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    shot = business_service.update_entity(session, Shot, shot_id, payload.model_dump(exclude_unset=True))
    return ok(serialize_model(shot), message="分镜已更新")


@router.delete("/shots/{shot_id}")
async def api_delete_shot(shot_id: str, session: Session = Depends(get_session)):
    shot = business_service.get_one(session, Shot, shot_id)
    if not shot:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    success = business_service.delete_entity(session, Shot, shot_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})
    return ok(None, message="分镜已删除")
