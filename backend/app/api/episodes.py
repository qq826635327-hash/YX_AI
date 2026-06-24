"""剧集 API 路由。"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.core.serialization import serialize_model, serialize_models
from app.db import get_session
from app.models import Asset, Episode, Shot
from app.schemas.business import EpisodeCreate, EpisodeUpdate
from app.schemas.common import ok
from app.services import business_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/projects/{project_id}/episodes", tags=["episodes"])


@router.get("")
async def api_list_episodes(project_id: str, session: Session = Depends(get_session)):
    items = business_service.list_by_project(session, Episode, project_id)
    return ok(serialize_models(items))


@router.post("")
async def api_create_episode(
    project_id: str,
    payload: EpisodeCreate,
    session: Session = Depends(get_session),
):
    ep = business_service.create_entity(session, Episode, project_id, payload.model_dump())
    return ok(serialize_model(ep), message="剧集已创建")


@router.get("/{episode_id}")
async def api_get_episode(project_id: str, episode_id: str, session: Session = Depends(get_session)):
    ep = business_service.get_one(session, Episode, episode_id)
    if not ep or ep.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    return ok(serialize_model(ep))


@router.patch("/{episode_id}")
async def api_update_episode(
    project_id: str,
    episode_id: str,
    payload: EpisodeUpdate,
    session: Session = Depends(get_session),
):
    ep = business_service.get_one(session, Episode, episode_id)
    if not ep or ep.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})

    # 检测 episode_no 变更
    old_episode_no = ep.episode_no
    new_episode_no = payload.model_dump(exclude_unset=True).get("episode_no", old_episode_no)

    if old_episode_no != new_episode_no:
        # 先重命名磁盘目录 + 暂存 Asset file_path 更新（不 commit）
        _rename_shots_dirs(session, project_id, episode_id, old_episode_no, new_episode_no, auto_commit=False)

    # 统一 commit：Episode 改名 + Asset 路径更新在同一事务
    ep = business_service.update_entity(session, Episode, episode_id, payload.model_dump(exclude_unset=True))
    return ok(serialize_model(ep), message="剧集已更新")


def _rename_shots_dirs(
    session: Session,
    project_id: str,
    episode_id: str,
    old_episode_no: int,
    new_episode_no: int,
    auto_commit: bool = True,
) -> None:
    """剧集 episode_no 变更时，更新其下所有分镜关联 Asset 的 file_path。

    新目录结构下分镜嵌套在 剧集/第X集/ 下，剧集目录重命名时分镜目录自动跟随移动，
    无需单独重命名分镜目录，只需更新 Asset file_path 中的前缀即可。

    事务策略：
    1. 查找该集下所有分镜关联的 Asset
    2. 将 file_path 中的 剧集/第{old_no}集/ 替换为 剧集/第{new_no}集/
    3. 若 auto_commit=True 则自动 commit

    Args:
        auto_commit: 是否自动 commit Asset 路径更新。False 时由调用方统一 commit。
    """
    old_prefix = f"剧集/第{old_episode_no}集/"
    new_prefix = f"剧集/第{new_episode_no}集/"

    shots = list(session.exec(
        select(Shot).where(Shot.episode_id == episode_id)
    ).all())

    updated = 0
    for shot in shots:
        assets = list(session.exec(
            select(Asset).where(
                Asset.project_id == project_id,
                Asset.target_id == shot.id,
                Asset.target_type.in_(("shot_first_frame", "shot_last_frame", "shot_video")),
            )
        ).all())
        for asset in assets:
            normalized = asset.file_path.replace("\\", "/")
            if normalized.startswith(old_prefix):
                asset.file_path = new_prefix + normalized[len(old_prefix):]
                session.add(asset)
                updated += 1
                logger.debug(f"[rename] Shot Asset path 更新: {normalized} → {asset.file_path}")

    if updated > 0:
        logger.info(f"[rename] 已暂存 {updated} 个分镜 Asset 的 file_path 更新")

    if auto_commit:
        session.commit()


@router.delete("/{episode_id}")
async def api_delete_episode(project_id: str, episode_id: str, session: Session = Depends(get_session)):
    ep = business_service.get_one(session, Episode, episode_id)
    if not ep or ep.project_id != project_id:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    success = business_service.delete_entity(session, Episode, episode_id)
    if not success:
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "剧集不存在"})
    return ok(None, message="剧集已删除")
