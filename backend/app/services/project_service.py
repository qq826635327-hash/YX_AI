"""项目业务服务。"""

from __future__ import annotations

import logging
import re
import shutil
from pathlib import Path
from typing import List, Optional

from sqlalchemy import func
from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import Project, gen_uuid
from app.schemas.project import ProjectCreate, ProjectUpdate

logger = logging.getLogger(__name__)


# ============================================================
# 项目目录初始化
# ============================================================

PROJECT_SUBDIRS = [
    "script",
    "assets/images/characters",
    "assets/images/scenes",
    "assets/images/props",
    "assets/images/first_frames",
    "assets/images/last_frames",
    "assets/videos/shot_videos",
    "assets/uploads",
    "exports",
    "logs",
]


def init_project_directory(root_path: Path) -> None:
    """初始化项目目录结构。"""
    root_path.mkdir(parents=True, exist_ok=True)
    for sub in PROJECT_SUBDIRS:
        (root_path / sub).mkdir(parents=True, exist_ok=True)


def _sanitize_name(name: str) -> str:
    """Sanitize 项目名，保留中文/字母/数字，其他变成下划线。"""
    # 保留中文、字母、数字、下划线
    s = re.sub(r'[^\w\u4e00-\u9fff]', '_', name)
    # 合并多个下划线
    s = re.sub(r'_+', '_', s)
    return s.strip('_')[:20]  # 限制长度，避免路径过长


def _resolve_project_root(project_name: str, custom_path: Optional[str] = None) -> Path:
    """计算项目根目录。文件夹名格式：项目名_短ID"""
    settings = get_settings()
    if custom_path:
        p = Path(custom_path)
        return p if p.is_absolute() else (settings.projects_root_abs / p)
    short_id = gen_uuid()[:8]
    folder_name = f"{_sanitize_name(project_name)}_{short_id}"
    return settings.projects_root_abs / folder_name


# ============================================================
# CRUD
# ============================================================

def create_project(session: Session, payload: ProjectCreate) -> Project:
    """新建项目。"""
    root_path = _resolve_project_root(payload.name, payload.root_path)
    init_project_directory(root_path)

    project = Project(
        name=payload.name,
        description=payload.description,
        cover_image=payload.cover_image,
        root_path=str(root_path),
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def get_project(session: Session, project_id: str) -> Optional[Project]:
    """获取项目详情。"""
    return session.get(Project, project_id)


def list_projects(
    session: Session,
    status: Optional[str] = None,
    keyword: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[List[Project], int]:
    """项目列表（带筛选与分页）。"""
    stmt = select(Project)
    if status:
        stmt = stmt.where(Project.status == status)
    if keyword:
        stmt = stmt.where(Project.name.contains(keyword))

    # 总数（复用 where 条件，避免重复构建）
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = session.exec(count_stmt).one()

    # 分页
    offset = (page - 1) * page_size
    stmt = stmt.order_by(Project.updated_at.desc()).offset(offset).limit(page_size)
    items = list(session.exec(stmt).all())
    return items, total


def update_project(session: Session, project_id: str, payload: ProjectUpdate) -> Optional[Project]:
    """更新项目。"""
    project = session.get(Project, project_id)
    if not project:
        return None

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(project, key, value)

    session.add(project)
    session.commit()
    session.refresh(project)
    return project


def delete_project(session: Session, project_id: str, delete_files: bool = False) -> bool:
    """删除项目。

    Args:
        delete_files: 是否同时删除项目目录文件（默认只删数据库记录）。
    """
    project = session.get(Project, project_id)
    if not project:
        return False

    # 先缓存项目根目录，再删除数据库记录（DB 级联删除子表）
    root: Optional[Path] = None
    if delete_files:
        root = Path(project.root_path).resolve()
        # 安全校验：确保删除路径在 projects_root_abs 下
        projects_root = get_settings().projects_root_abs.resolve()
        if not root.is_relative_to(projects_root):
            logger.warning(f"项目目录超出项目根目录范围，仅删除数据库记录，不删除文件: {root}")
            root = None  # 不删除文件，但继续删除数据库记录

    # 手动删除子表记录，避免 SQLite 外键级联在循环引用（assets↔tasks）下失败
    from app.models import Asset, Character, Episode, Prop, Scene, ScriptDocument, Shot
    from app.models.shot_reference import ShotCharacter, ShotProp, ShotScene
    from app.models.task import GenerationTask
    from app.models.task_log import TaskLog
    from sqlalchemy import delete as sa_delete

    # 1. 查出所有 episode_id 和 shot_id
    ep_ids = list(session.exec(select(Episode.id).where(Episode.project_id == project_id)).all())
    shot_ids = list(session.exec(select(Shot.id).where(Shot.project_id == project_id)).all())

    # 2. 删除 shot 关联表
    if shot_ids:
        session.exec(sa_delete(ShotCharacter).where(ShotCharacter.shot_id.in_(shot_ids)))
        session.exec(sa_delete(ShotScene).where(ShotScene.shot_id.in_(shot_ids)))
        session.exec(sa_delete(ShotProp).where(ShotProp.shot_id.in_(shot_ids)))

    # 3. 查出所有 task_id（先于 assets 删除，因为 assets.task_id SET NULL）
    task_ids = list(session.exec(select(GenerationTask.id).where(GenerationTask.project_id == project_id)).all())

    # 4. 删除 task_logs（cascade on task）
    if task_ids:
        session.exec(sa_delete(TaskLog).where(TaskLog.task_id.in_(task_ids)))

    # 5. 删除 assets（task_id 会被 SET NULL，但 assets 也要删）
    session.exec(sa_delete(Asset).where(Asset.project_id == project_id))

    # 6. 删除 tasks
    if task_ids:
        session.exec(sa_delete(GenerationTask).where(GenerationTask.id.in_(task_ids)))

    # 7. 删除 shots
    if shot_ids:
        session.exec(sa_delete(Shot).where(Shot.id.in_(shot_ids)))

    # 8. 删除 characters/scenes/props
    session.exec(sa_delete(Character).where(Character.project_id == project_id))
    session.exec(sa_delete(Scene).where(Scene.project_id == project_id))
    session.exec(sa_delete(Prop).where(Prop.project_id == project_id))

    # 9. 删除 script
    session.exec(sa_delete(ScriptDocument).where(ScriptDocument.project_id == project_id))

    # 10. 删除 episodes
    if ep_ids:
        session.exec(sa_delete(Episode).where(Episode.id.in_(ep_ids)))

    # 11. 最后删除 project
    session.delete(project)
    session.commit()

    if delete_files and root and root.exists() and root.is_dir():
        shutil.rmtree(root, ignore_errors=True)
        logger.info(f"已删除项目目录: {root}")

    return True


def update_project_stats(session: Session, project_id: str) -> Optional[Project]:
    """更新项目统计数据（角色数、场景数等）。使用 SQL COUNT 避免全表加载。"""
    from app.models import Character, Episode, Prop, Scene, Shot

    project = session.get(Project, project_id)
    if not project:
        return None

    project.character_count = session.exec(
        select(func.count()).select_from(Character).where(Character.project_id == project_id)
    ).one()
    project.scene_count = session.exec(
        select(func.count()).select_from(Scene).where(Scene.project_id == project_id)
    ).one()
    project.prop_count = session.exec(
        select(func.count()).select_from(Prop).where(Prop.project_id == project_id)
    ).one()
    project.episode_count = session.exec(
        select(func.count()).select_from(Episode).where(Episode.project_id == project_id)
    ).one()
    project.shot_count = session.exec(
        select(func.count()).select_from(Shot).where(Shot.project_id == project_id)
    ).one()

    session.add(project)
    session.commit()
    session.refresh(project)
    return project
