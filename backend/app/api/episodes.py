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
from app.services.asset_service import get_project_root

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
    """剧集 episode_no 变更时，重命名其下所有分镜目录并更新 Asset file_path。

    事务策略：
    1. 先收集所有需要重命名的目录与对应的 Asset 记录
    2. 执行文件系统重命名，记录已成功重命名的目录
    3. 更新 DB 中 Asset 的 file_path
    4. 若中途失败，尝试回滚已重命名的目录

    Args:
        auto_commit: 是否自动 commit Asset 路径更新。False 时由调用方统一 commit。
    """
    project_root = get_project_root(project_id, session)
    if not project_root:
        return

    shots = list(session.exec(
        select(Shot).where(Shot.episode_id == episode_id)
    ).all())

    # 收集待重命名项：[(old_dir, new_dir, shot, old_prefix, new_prefix), ...]
    rename_plan: list[tuple] = []
    for shot in shots:
        old_dirname = f"第{old_episode_no}集_{shot.shot_no}"
        new_dirname = f"第{new_episode_no}集_{shot.shot_no}"
        old_dir = project_root / "分镜" / old_dirname
        new_dir = project_root / "分镜" / new_dirname
        if not old_dir.exists():
            continue
        if new_dir.exists():
            logger.warning(f"[rename] 目标目录已存在，跳过: {new_dir}")
            continue
        old_prefix = f"分镜/{old_dirname}/"
        new_prefix = f"分镜/{new_dirname}/"
        rename_plan.append((old_dir, new_dir, shot, old_prefix, new_prefix))

    if not rename_plan:
        return

    # 执行重命名，记录已成功的项以便回滚
    done: list[tuple] = []
    try:
        for old_dir, new_dir, shot, old_prefix, new_prefix in rename_plan:
            old_dir.rename(new_dir)
            logger.info(f"[rename] 分镜目录已重命名: {old_dir} → {new_dir}")
            done.append((old_dir, new_dir, shot, old_prefix, new_prefix))
    except OSError as e:
        # 回滚已重命名的目录
        logger.error(f"[rename] 重命名失败，开始回滚: {e}")
        for old_dir, new_dir, shot, old_prefix, new_prefix in reversed(done):
            try:
                new_dir.rename(old_dir)
                logger.info(f"[rename] 回滚: {new_dir} → {old_dir}")
            except OSError as rb_err:
                logger.error(f"[rename] 回滚失败: {rb_err}")
        raise HTTPException(
            status_code=500,
            detail={"error": "rename_failed", "message": f"分镜目录重命名失败: {e}"},
        )

    # 所有重命名成功，暂存 Asset file_path 更新
    for old_dir, new_dir, shot, old_prefix, new_prefix in done:
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
