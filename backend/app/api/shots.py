"""分镜 API 路由。"""

from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Episode, Shot
from app.schemas.business import ShotCreate, ShotUpdate
from app.schemas.common import ok
from app.services import business_service
from app.services.business_service import _rename_entity_dir

logger = logging.getLogger(__name__)

router = APIRouter(tags=["shots"])


class ReorderItem(BaseModel):
    id: str
    sort_order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]


@router.get("/episodes/{episode_id}/shots")
async def api_list_shots(episode_id: str, session: Session = Depends(get_session)):
    """按剧集列出分镜。"""
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    items = business_service.list_shots_by_episode(session, episode_id)
    return ok(serialize_models(items))


@router.post("/episodes/{episode_id}/shots/reorder")
async def api_reorder_shots(
    episode_id: str,
    payload: ReorderRequest,
    session: Session = Depends(get_session),
):
    """批量更新分镜排序（拖拽排序后调用）。同时自动重排 shot_no 并重命名磁盘目录。"""
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})

    # 收集旧的 shot_no → 目录名映射
    from sqlmodel import select
    shots = list(session.exec(
        select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.sort_order)
    ).all())
    old_shot_nos = {s.id: s.shot_no for s in shots}
    project_id = episode.project_id

    # 更新 sort_order
    for item in payload.items:
        shot = session.get(Shot, item.id)
        if shot and shot.episode_id == episode_id:
            shot.sort_order = item.sort_order
            session.add(shot)

    session.commit()

    # 自动重排 shot_no：按 sort_order 排序后重新编号
    shots = list(session.exec(
        select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.sort_order)
    ).all())
    for idx, shot in enumerate(shots):
        shot.shot_no = idx + 1
        session.add(shot)
    session.commit()

    # 重命名磁盘目录 + 更新 Asset file_path
    for shot in shots:
        old_no = old_shot_nos.get(shot.id)
        if old_no is not None and old_no != shot.shot_no:
            old_dirname = f"分镜{old_no:03d}"
            new_dirname = f"分镜{shot.shot_no:03d}"
            _rename_entity_dir(
                session, Shot, shot.id, project_id,
                old_dirname, new_dirname, auto_commit=False,
            )
    session.commit()

    return ok(serialize_models(shots), message="排序已更新")


@router.post("/episodes/{episode_id}/shots")
async def api_create_shot(
    episode_id: str,
    payload: ShotCreate,
    session: Session = Depends(get_session),
):
    """新建分镜，并自动重排所有分镜编号。"""
    episode = session.get(Episode, episode_id)
    if not episode:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    project_id = episode.project_id
    shot = business_service.create_shot(session, episode_id, project_id, payload.model_dump())

    # 自动重排 shot_no：按 sort_order 排序后重新编号 + 重命名目录
    from sqlmodel import select
    shots = list(session.exec(
        select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.sort_order, Shot.created_at)
    ).all())
    old_shot_nos = {s.id: s.shot_no for s in shots}
    for idx, s in enumerate(shots):
        s.shot_no = idx + 1
        session.add(s)
    session.commit()

    # 重命名磁盘目录 + 更新 Asset file_path
    for s in shots:
        old_no = old_shot_nos.get(s.id)
        if old_no is not None and old_no != s.shot_no:
            old_dirname = f"分镜{old_no:03d}"
            new_dirname = f"分镜{s.shot_no:03d}"
            _rename_entity_dir(
                session, Shot, s.id, project_id,
                old_dirname, new_dirname, auto_commit=False,
            )
    session.commit()

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
    episode_id = shot.episode_id
    episode = session.get(Episode, episode_id)
    project_id = episode.project_id if episode else None
    success = business_service.delete_entity(session, Shot, shot_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "分镜不存在"})

    # 删除后自动重排 shot_no + 重命名磁盘目录
    from sqlmodel import select
    remaining = list(session.exec(
        select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.sort_order, Shot.created_at)
    ).all())
    old_shot_nos = {s.id: s.shot_no for s in remaining}
    for idx, s in enumerate(remaining):
        s.shot_no = idx + 1
        session.add(s)
    session.commit()

    # 重命名磁盘目录 + 更新 Asset file_path
    if project_id:
        for s in remaining:
            old_no = old_shot_nos.get(s.id)
            if old_no is not None and old_no != s.shot_no:
                old_dirname = f"分镜{old_no:03d}"
                new_dirname = f"分镜{s.shot_no:03d}"
                _rename_entity_dir(
                    session, Shot, s.id, project_id,
                    old_dirname, new_dirname, auto_commit=False,
                )
        session.commit()

    return ok(None, message="分镜已删除")
