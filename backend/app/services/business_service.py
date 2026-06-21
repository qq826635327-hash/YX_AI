"""业务实体通用 CRUD 服务（角色/场景/道具/剧集/分镜）。

这些实体结构高度相似，统一抽象减少重复代码。
删除实体时同步清理磁盘上的图片/视频/prompt 文件。

注意：原 CharacterService/SceneService/PropService/EpisodeService/ShotService
五个 Service 模板类已于 2026-06-20 删除。直接调用本模块的通用函数即可。
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import List, Optional, Type, TypeVar

from sqlmodel import Session, select

from app.models import Character, Episode, Prop, Scene, Shot
from app.services.asset_service import delete_asset, get_project_root, resolve_asset_path
from app.services.project_service import update_project_stats

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 模块目录映射（Model → 中文名）
MODULE_DIR_MAP = {
    Character: "角色",
    Scene: "场景",
    Prop: "道具",
    Shot: "分镜",
}

# target_type 字符串映射（用于查询关联的 Asset）
TARGET_TYPE_MAP = {
    Character: "character",
    Scene: "scene",
    Prop: "prop",
    Shot: "shot",
}

# target_type → 模块目录名（用于 execute_task 等非 Model 场景）
TARGET_TYPE_DIR_MAP = {
    "character": "角色",
    "scene": "场景",
    "prop": "道具",
    "shot_first_frame": "分镜",
    "shot_last_frame": "分镜",
    "shot_video": "分镜",
}


def sanitize_name(name: str) -> str:
    """清洗实体名称用于目录名。"""
    for ch in ('/', '\\', ':', '*', '?', '"', '<', '>', '|'):
        name = name.replace(ch, '_')
    return name[:50] or "unknown"


def _compute_dirname(model: Type[T], entity, session: Session = None) -> Optional[str]:
    """根据实体当前字段值计算目录名。

    对于角色/场景/道具，直接用 sanitize_name(name)。
    对于分镜，需要查关联 Episode 的 episode_no，因此需要 session。
    """
    if model in (Character, Scene, Prop):
        name = getattr(entity, "name", None)
        return sanitize_name(name) if name else None
    elif model is Shot and session:
        episode_id = getattr(entity, "episode_id", None)
        shot_no = getattr(entity, "shot_no", None)
        if episode_id and shot_no is not None:
            ep = session.get(Episode, episode_id)
            if ep:
                return f"第{ep.episode_no}集_{shot_no}"
    return None


def _rename_entity_dir(
    session: Session,
    model: Type[T],
    entity_id: str,
    project_id: str,
    old_dirname: str,
    new_dirname: str,
    auto_commit: bool = True,
) -> None:
    """重命名实体磁盘目录，并更新关联 Asset 的 file_path。

    Args:
        auto_commit: 是否在更新 Asset 路径后自动 commit。
                    False 时由调用方统一 commit，保证事务原子性。
    """
    from app.models import Asset

    project_root = get_project_root(project_id, session)
    if not project_root:
        return

    module_dir_name = MODULE_DIR_MAP.get(model)
    if not module_dir_name:
        return

    old_dir = project_root / module_dir_name / old_dirname
    new_dir = project_root / module_dir_name / new_dirname

    if not old_dir.exists():
        logger.debug(f"[rename] 旧目录不存在，跳过: {old_dir}")
        return

    if new_dir.exists():
        logger.warning(f"[rename] 新目录已存在，跳过重命名: {new_dir}")
        return

    # ── 重命名磁盘目录 ─────────────────────────────────
    try:
        # os.replace 是原子操作（同文件系统），比 Path.rename 更安全
        import os
        os.replace(str(old_dir), str(new_dir))
        logger.info(f"[rename] 目录已重命名: {old_dir} → {new_dir}")
    except FileNotFoundError:
        logger.warning(f"[rename] 旧目录不存在（并发删除？）: {old_dir}")
        return
    except OSError as e:
        logger.error(f"[rename] 重命名目录失败: {old_dir} → {new_dir}: {e}")
        return

    # ── 更新 Asset 表中的 file_path ──────────────────────
    # 旧路径前缀：角色/旧名/  →  新路径前缀：角色/新名/
    old_prefix = f"{module_dir_name}/{old_dirname}/"
    new_prefix = f"{module_dir_name}/{new_dirname}/"

    target_type = TARGET_TYPE_MAP.get(model)
    if not target_type:
        return

    # 查找所有关联 Asset
    if model is Shot:
        # 分镜的 target_type 有 shot_first_frame / shot_last_frame / shot_video
        assets = list(session.exec(
            select(Asset).where(
                Asset.project_id == project_id,
                Asset.target_type.in_(("shot_first_frame", "shot_last_frame", "shot_video")),
                Asset.target_id == entity_id,
            )
        ).all())
    else:
        assets = list(session.exec(
            select(Asset).where(
                Asset.project_id == project_id,
                Asset.target_type == target_type,
                Asset.target_id == entity_id,
            )
        ).all())

    updated = 0
    for asset in assets:
        # 统一用 / 分隔符比较
        normalized_path = asset.file_path.replace("\\", "/")
        if normalized_path.startswith(old_prefix):
            new_path = new_prefix + normalized_path[len(old_prefix):]
            asset.file_path = new_path
            session.add(asset)
            updated += 1
            logger.debug(f"[rename] Asset path 更新: {asset.file_path} → {new_path}")

    if updated > 0 and auto_commit:
        session.commit()
        logger.info(f"[rename] 已更新 {updated} 个 Asset 的 file_path")
    elif updated > 0:
        logger.info(f"[rename] 已暂存 {updated} 个 Asset 的 file_path 更新（等待调用方 commit）")


def get_entity_dirname(session, target_type: str, target_id: str) -> Optional[str]:
    """根据 target_type + target_id 计算实体对应的磁盘目录名。

    统一入口，execute_task.py 和本模块共用，避免逻辑分散。
    """
    from app.models import Episode, Shot

    try:
        if target_type == "character":
            e = session.get(Character, target_id)
            return sanitize_name(e.name) if e and e.name else None
        elif target_type == "scene":
            e = session.get(Scene, target_id)
            return sanitize_name(e.name) if e and e.name else None
        elif target_type == "prop":
            e = session.get(Prop, target_id)
            return sanitize_name(e.name) if e and e.name else None
        elif target_type == "shot" or target_type in ("shot_first_frame", "shot_last_frame", "shot_video"):
            shot = session.get(Shot, target_id)
            if shot:
                ep = session.get(Episode, shot.episode_id)
                ep_no = ep.episode_no if ep else "?"
                return f"第{ep_no}集_{shot.shot_no}"
            return None
    except Exception:
        return None
    return None


# ============================================================
# 通用 CRUD（直接调用这些函数，无需 Service 包装类）
# ============================================================

def list_by_project(
    session: Session,
    model: Type[T],
    project_id: str,
    order_field: str = "sort_order",
) -> List[T]:
    """按项目列出实体。"""
    stmt = select(model).where(model.project_id == project_id)  # type: ignore[attr-defined]
    order_col = getattr(model, order_field, None)
    if order_col is not None:
        stmt = stmt.order_by(order_col)
    return list(session.exec(stmt).all())


def get_one(session: Session, model: Type[T], entity_id: str) -> Optional[T]:
    """获取单个实体。"""
    return session.get(model, entity_id)


def create_entity(session: Session, model: Type[T], project_id: str, data: dict) -> T:
    """新建实体。"""
    entity = model(project_id=project_id, **data)  # type: ignore[call-arg]
    session.add(entity)
    session.commit()
    session.refresh(entity)
    update_project_stats(session, project_id)
    return entity


def update_entity(session: Session, model: Type[T], entity_id: str, data: dict) -> Optional[T]:
    """更新实体（支持设置字段为 None）。

    当实体名称变更时，同步重命名磁盘目录并更新关联 Asset 的 file_path。
    事务策略：先重命名磁盘（best-effort），再统一 commit DB（实体 + Asset 路径），
    保证 DB 状态原子性。磁盘重命名失败只记日志，不回滚 DB（磁盘可后续修复）。
    """
    entity = session.get(model, entity_id)
    if not entity:
        return None

    # ── 检测名称变更，准备重命名目录 ──────────────────────
    old_dirname = _compute_dirname(model, entity, session)
    project_id = getattr(entity, "project_id", None)

    # 应用变更到内存中的实体（不 commit）
    for key, value in data.items():
        setattr(entity, key, value)
    session.add(entity)

    # 计算新目录名（基于内存中的新字段值）
    new_dirname = _compute_dirname(model, entity, session)

    # 名称变更 → 先重命名磁盘目录 + 暂存 Asset file_path 更新（不 commit）
    if project_id and old_dirname and new_dirname and old_dirname != new_dirname:
        _rename_entity_dir(session, model, entity_id, project_id, old_dirname, new_dirname, auto_commit=False)

    # 统一 commit：实体改名 + Asset 路径更新在同一事务
    session.commit()
    session.refresh(entity)

    return entity


def delete_entity(session: Session, model: Type[T], entity_id: str) -> bool:
    """删除实体，并同步清理磁盘上的所有关联文件。

    清理范围：
    1. 关联 Asset 的磁盘文件（images/ videos/）
    2. 对应的 prompt 文件（prompts/xxx.txt）
    3. Asset 数据库记录
    4. 实体目录（rmtree 兜底清理）
    5. Episode 删除时级联删除子 Shot 及其关联记录
    """
    entity = session.get(model, entity_id)
    if not entity:
        return False

    project_id = getattr(entity, "project_id", None)
    assets_to_delete: List = []

    # ── Episode 特殊处理：先级联删除子 Shot ──────────────
    if model is Episode and project_id:
        _cascade_delete_shots_by_episode(session, entity_id, project_id)

    # ── 收集关联的 Asset ─────────────────────────────────
    if project_id:
        from app.models import Asset

        target_type = TARGET_TYPE_MAP.get(model)
        if target_type:
            if model is Shot:
                # 分镜的 target_type 有 shot_first_frame / shot_last_frame / shot_video
                assets_to_delete = list(session.exec(
                    select(Asset).where(
                        Asset.target_type.in_(("shot_first_frame", "shot_last_frame", "shot_video")),
                        Asset.target_id == entity_id,
                    )
                ).all())
            else:
                assets_to_delete = list(session.exec(
                    select(Asset).where(
                        Asset.target_type == target_type,
                        Asset.target_id == entity_id,
                    )
                ).all())

        if model in (Character, Scene, Prop):
            img_asset_id = getattr(entity, "image_asset_id", None)
            if img_asset_id:
                existing_ids = {a.id for a in assets_to_delete}
                if img_asset_id not in existing_ids:
                    asset = session.get(Asset, img_asset_id)
                    if asset:
                        assets_to_delete.append(asset)

    # ── 删除关联的 Asset（含外键清理 + 物理文件）─────────
    if assets_to_delete:
        for asset in assets_to_delete:
            delete_asset(session, asset.id, delete_file=True, auto_commit=False)
        logger.info(f"已删除 {len(assets_to_delete)} 个关联素材")

    # ── rmtree 实体目录（兜底清理）───────────────────────
    if project_id and model in MODULE_DIR_MAP:
        project_root = get_project_root(project_id, session)
        if project_root:
            dir_name = get_entity_dirname(session, TARGET_TYPE_MAP.get(model, ""), entity_id)
            if dir_name:
                entity_dir = project_root / MODULE_DIR_MAP[model] / dir_name
                if entity_dir.exists():
                    shutil.rmtree(str(entity_dir), ignore_errors=True)
                    logger.info(f"已删除实体目录: {entity_dir}")

    # ── 删除实体 DB 记录 ────────────────────────────────
    session.delete(entity)
    session.commit()
    if project_id:
        update_project_stats(session, project_id)
    return True


def _cascade_delete_shots_by_episode(session: Session, episode_id: str, project_id: str) -> None:
    """级联删除 Episode 下的所有 Shot 及其关联记录。

    SQLite 外键级联在循环引用（assets↔tasks）下失败，
    需要手动按依赖顺序删除：shot_references → task_logs → assets → tasks → shots
    """
    from sqlalchemy import delete as sa_delete
    from app.models import Asset, GenerationTask, TaskLog
    from app.models.shot_reference import ShotCharacter, ShotScene, ShotProp

    shot_ids = list(session.exec(
        select(Shot.id).where(Shot.episode_id == episode_id)
    ).all())
    if not shot_ids:
        return

    logger.info(f"[cascade] 级联删除 Episode {episode_id} 下的 {len(shot_ids)} 个 Shot")

    # 1. 删除分镜关联表
    session.exec(sa_delete(ShotCharacter).where(ShotCharacter.shot_id.in_(shot_ids)))
    session.exec(sa_delete(ShotScene).where(ShotScene.shot_id.in_(shot_ids)))
    session.exec(sa_delete(ShotProp).where(ShotProp.shot_id.in_(shot_ids)))

    # 2. 删除分镜关联的 Asset（含物理文件）
    shot_assets = list(session.exec(
        select(Asset).where(
            Asset.project_id == project_id,
            Asset.target_type.in_(("shot_first_frame", "shot_last_frame", "shot_video")),
            Asset.target_id.in_(shot_ids),
        )
    ).all())
    for asset in shot_assets:
        delete_asset(session, asset.id, delete_file=True, auto_commit=False)

    # 3. 删除分镜关联的 TaskLog + Task
    task_ids = list(session.exec(
        select(GenerationTask.id).where(
            GenerationTask.project_id == project_id,
            GenerationTask.target_id.in_(shot_ids),
        )
    ).all())
    if task_ids:
        session.exec(sa_delete(TaskLog).where(TaskLog.task_id.in_(task_ids)))
        session.exec(sa_delete(GenerationTask).where(GenerationTask.id.in_(task_ids)))

    # 4. 删除 Shot 目录
    project_root = get_project_root(project_id, session)
    if project_root:
        for shot_id in shot_ids:
            dir_name = get_entity_dirname(session, "shot", shot_id)
            if dir_name:
                shot_dir = project_root / "分镜" / dir_name
                if shot_dir.exists():
                    shutil.rmtree(str(shot_dir), ignore_errors=True)

    # 5. 批量删除 Shot 记录
    session.exec(sa_delete(Shot).where(Shot.id.in_(shot_ids)))

    logger.info(f"[cascade] 已级联删除 {len(shot_ids)} 个 Shot 及其关联记录")


# ============================================================
# 分镜特殊处理（属于剧集）
# ============================================================

def list_shots_by_episode(session: Session, episode_id: str) -> List[Shot]:
    """按剧集列出分镜。"""
    stmt = select(Shot).where(Shot.episode_id == episode_id).order_by(Shot.sort_order, Shot.shot_no)
    return list(session.exec(stmt).all())


def create_shot(session: Session, episode_id: str, project_id: str, data: dict) -> Shot:
    """新建分镜。"""
    shot = Shot(episode_id=episode_id, project_id=project_id, **data)
    session.add(shot)
    session.commit()
    session.refresh(shot)
    update_project_stats(session, project_id)
    return shot
