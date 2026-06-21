"""素材服务：文件管理、读写、缩略图。"""

from __future__ import annotations

import logging
import mimetypes
import os
import re
import shutil
import time
from pathlib import Path
from typing import List, Optional

from sqlmodel import Session, select

from app.core.config import get_settings
from app.models import Asset

logger = logging.getLogger(__name__)


# ============================================================
# 路径工具
# ============================================================

def get_project_root(project_id: str, session: Session) -> Optional[Path]:
    """获取项目根目录。"""
    from app.models import Project

    project = session.get(Project, project_id)
    if not project:
        return None
    return Path(project.root_path)


def _sanitize_filename(filename: str) -> str:
    """清洗文件名，移除路径组件和危险字符。"""
    # 取纯文件名，防止路径穿越
    name = Path(filename).name
    # 移除不可见字符和路径分隔符
    name = re.sub(r'[/\\]', '_', name)
    # 防止以 . 开头的隐藏文件
    if name.startswith('.'):
        name = '_' + name
    return name or 'upload.bin'


def resolve_asset_path(project_root: Path, file_path: str) -> Path:
    """解析素材文件绝对路径，强制限制在项目根目录内。"""
    p = Path(file_path)
    # 禁止直接使用绝对路径——所有素材路径必须是相对路径
    if p.is_absolute():
        # 尝试将绝对路径转换为相对于 project_root 的路径
        try:
            rel = p.relative_to(project_root.resolve())
            resolved = (project_root / rel).resolve()
        except ValueError:
            raise ValueError(f"素材路径超出项目目录范围: {file_path}")
    else:
        resolved = (project_root / file_path).resolve()

    # 二次校验：确保解析后仍在项目根目录下
    if not resolved.is_relative_to(project_root.resolve()):
        raise ValueError(f"素材路径非法（路径穿越）: {file_path}")

    return resolved


# ============================================================
# CRUD
# ============================================================

def list_assets(
    session: Session,
    project_id: str,
    category: Optional[str] = None,
    asset_type: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
) -> List[Asset]:
    stmt = select(Asset).where(Asset.project_id == project_id)
    if category:
        stmt = stmt.where(Asset.category == category)
    if asset_type:
        stmt = stmt.where(Asset.asset_type == asset_type)
    if target_type:
        stmt = stmt.where(Asset.target_type == target_type)
    if target_id:
        stmt = stmt.where(Asset.target_id == target_id)
    stmt = stmt.order_by(Asset.created_at.desc())
    return list(session.exec(stmt).all())


def get_asset(session: Session, asset_id: str) -> Optional[Asset]:
    """获取素材记录。"""
    return session.get(Asset, asset_id)


def create_asset_record(
    session: Session,
    project_id: str,
    asset_type: str,
    category: str,
    file_path: str,
    **extra,
) -> Asset:
    """创建素材记录。"""
    p = Path(file_path)
    asset = Asset(
        project_id=project_id,
        asset_type=asset_type,
        category=category,
        file_path=file_path,
        file_name=p.name,
        file_size=extra.get("file_size"),
        mime_type=extra.get("mime_type") or mimetypes.guess_type(p.name)[0],
        width=extra.get("width"),
        height=extra.get("height"),
        duration=extra.get("duration"),
        provider_id=extra.get("provider_id"),
        workflow_mapping_id=extra.get("workflow_mapping_id"),
        task_id=extra.get("task_id"),
        status=extra.get("status", "ready"),
        target_type=extra.get("target_type"),
        target_id=extra.get("target_id"),
    )
    session.add(asset)
    session.commit()
    session.refresh(asset)
    return asset


def delete_asset(session: Session, asset_id: str, delete_file: bool = False, auto_commit: bool = True) -> bool:
    """删除素材记录，并清除所有外键引用。

    修复历史（2026-06-20）：
        原实现 commit 后访问 asset.project_id 触发 lazy load，
        在 Windows 上路径解析或 unlink 失败后留下 500。
        现改为：先缓存所有所需字段，再分阶段 commit，文件删除独立 try-except。
    """
    asset = session.get(Asset, asset_id)
    if not asset:
        return False

    # ── 在 commit 前缓存所有需要后续访问的字段 ──
    # SQLModel 默认 expire_on_commit=True，commit 后访问属性可能触发额外的 SQL 查询
    # 缓存字段避免 commit 后的二次访问
    project_id = asset.project_id
    file_path = asset.file_path
    asset_id_str = str(asset.id)

    from app.models import Character, Scene, Prop, Shot, GenerationTask, Project

    # 1. 角色/场景/道具 主图
    for Model in (Character, Scene, Prop):
        refs = list(session.exec(
            select(Model).where(Model.image_asset_id == asset_id_str)
        ).all())
        for ref in refs:
            ref.image_asset_id = None
            session.add(ref)

    # 2. 镜头（分三次查，避免 OR 语法问题）
    for field_name in ("first_frame_asset_id", "last_frame_asset_id", "video_asset_id"):
        shots = list(session.exec(
            select(Shot).where(getattr(Shot, field_name) == asset_id_str)
        ).all())
        for shot in shots:
            setattr(shot, field_name, None)
            session.add(shot)

    # 3. 生成任务输出素材
    tasks = list(session.exec(
        select(GenerationTask).where(GenerationTask.output_asset_id == asset_id_str)
    ).all())
    for t in tasks:
        t.output_asset_id = None
        session.add(t)

    # 第一次 commit：清除外键引用
    if auto_commit:
        try:
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"删除素材外键清理失败 {asset_id_str}: {e}")
            raise

    # ── 物理文件删除（独立 try-except，不影响数据库操作）──
    if delete_file and file_path:
        try:
            project = session.get(Project, project_id)
            if project:
                full_path = resolve_asset_path(Path(project.root_path), file_path)
                if full_path.exists():
                    try:
                        full_path.unlink(missing_ok=True)
                        logger.info(f"已删除文件: {full_path}")
                    except PermissionError as e:
                        logger.warning(f"文件被占用，跳过删除: {full_path} - {e}")
                    except OSError as e:
                        logger.warning(f"删除文件失败: {full_path} - {e}")

                # 同步删除对应的 prompt 记录文件
                parent_dir = full_path.parent
                if parent_dir.name in ("images", "videos"):
                    prompt_path = parent_dir.parent / "prompts" / (full_path.stem + ".txt")
                    if prompt_path.exists():
                        try:
                            prompt_path.unlink(missing_ok=True)
                            logger.info(f"已删除 prompt 文件: {prompt_path}")
                        except OSError as e:
                            logger.warning(f"删除 prompt 失败: {prompt_path} - {e}")
        except ValueError as e:
            # 路径非法（路径穿越等）
            logger.warning(f"文件路径非法，跳过物理删除 {file_path}: {e}")
        except Exception as e:
            # 其他错误也不影响数据库操作
            logger.error(f"物理文件删除异常（已忽略）: {e}", exc_info=True)

    # ── 删除数据库记录 ──
    # 重新查询以避免 commit 后 expire 问题
    asset = session.get(Asset, asset_id_str)
    if asset:
        session.delete(asset)
        if auto_commit:
            try:
                session.commit()
            except Exception as e:
                session.rollback()
                logger.error(f"删除素材记录 commit 失败 {asset_id_str}: {e}")
                raise
    return True


# ============================================================
# 文件读写
# ============================================================

def _validate_file_extension(filename: str, allowed_types: List[str]) -> bool:
    """校验文件扩展名是否在允许列表中。"""
    if not allowed_types:
        return True
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''
    return ext in allowed_types


def save_uploaded_file(
    project_root: Path,
    category: str,
    filename: str,
    content: bytes,
    max_size: int = 200 * 1024 * 1024,  # 200MB 上限
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    session: Optional[Session] = None,
) -> str:
    """保存上传文件，返回相对项目根目录的路径。

    当提供了 target_type + target_id 时，文件存入实体专属目录（与 AI 生图一致）：
      角色/{name}/images/
      场景/{name}/images/
      道具/{name}/images/

    否则存入通用 assets/ 目录。
    """
    # 校验文件大小
    if len(content) > max_size:
        raise ValueError(f"文件过大: {len(content)} 字节（上限 {max_size} 字节）")

    # 清洗文件名，防止路径穿越
    safe_name = _sanitize_filename(filename)

    # 校验文件类型
    settings = get_settings()
    all_allowed = (
        settings.storage.allowed_image_types + settings.storage.allowed_video_types
    )
    if all_allowed and not _validate_file_extension(safe_name, all_allowed):
        raise ValueError(f"不允许的文件类型: {safe_name}")

    # ── 有目标实体时，用实体专属目录 ──────────────────────
    if target_type and target_id and session:
        module_dir_map = {
            "character": "角色",
            "scene": "场景",
            "prop": "道具",
        }
        module_dir = module_dir_map.get(target_type)
        if module_dir:
            entity_name = _get_entity_name_for_upload(session, target_type, target_id)
            sub_dir = f"{module_dir}/{entity_name}/images"
            target_dir = project_root / sub_dir
            target_dir.mkdir(parents=True, exist_ok=True)
            safe_name = f"{int(time.time())}_{safe_name}"
            target_path = target_dir / safe_name
            resolved_target = target_path.resolve()
            if not resolved_target.is_relative_to(project_root.resolve()):
                raise ValueError("上传路径非法（路径穿越）")
            try:
                resolved_target.write_bytes(content)
            except (OSError, PermissionError) as e:
                logger.error(f"文件写入失败: {resolved_target}: {e}")
                raise
            logger.info(f"文件已保存（实体目录）: {resolved_target}")
            return str(resolved_target.relative_to(project_root.resolve())).replace("\\", "/")

    # ── 无目标实体或无法解析时，走通用 assets 目录 ──────────
    if category in ("character", "scene", "prop", "first_frame", "last_frame"):
        sub_dir = f"assets/images/{category}s"
    elif category == "shot_video":
        sub_dir = "assets/videos/shot_videos"
    else:
        sub_dir = "assets/uploads"

    target_dir = project_root / sub_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    # 避免重名：加时间戳
    safe_name = f"{int(time.time())}_{safe_name}"
    target_path = target_dir / safe_name

    # 路径穿越校验
    resolved_target = target_path.resolve()
    if not resolved_target.is_relative_to(project_root.resolve()):
        raise ValueError("上传路径非法（路径穿越）")

    try:
        resolved_target.write_bytes(content)
    except (OSError, PermissionError) as e:
        logger.error(f"文件写入失败: {resolved_target}: {e}")
        raise
    logger.info(f"文件已保存（通用目录）: {resolved_target}")

    # 返回相对路径
    return str(resolved_target.relative_to(project_root.resolve())).replace("\\", "/")


def _get_entity_name_for_upload(session: Session, target_type: str, target_id: str) -> str:
    """根据实体类型和 ID 查询实体名称。"""
    from app.services.business_service import get_entity_dirname

    dirname = get_entity_dirname(session, target_type, target_id)
    return dirname or target_id[:8]


def get_asset_file_path(session: Session, asset_id: str) -> Optional[tuple[Path, Asset]]:
    """获取素材文件绝对路径与记录。"""
    asset = session.get(Asset, asset_id)
    if not asset:
        return None
    from app.models import Project

    project = session.get(Project, asset.project_id)
    if not project:
        return None
    full_path = resolve_asset_path(Path(project.root_path), asset.file_path)
    return full_path, asset


# ============================================================
# 同步清理：扫描 DB 记录，删除磁盘文件已丢失的记录
# ============================================================

def sync_assets(session: Session, project_id: str) -> dict:
    """双向同步项目素材：

    1. 清理：删除磁盘文件已丢失的 DB 记录
    2. 发现：扫描磁盘文件，为没有 DB 记录的文件自动创建 Asset 并回填到实体

    返回报告：
      - checked: 检查的 DB 记录数
      - cleaned: 清理的 DB 记录数
      - discovered: 新发现的磁盘文件数
      - errors: 处理时出错的记录数
      - details: 变更详情列表
    """
    from app.models import Project, Character, Scene, Prop, Shot, Episode
    from app.services.business_service import get_entity_dirname, TARGET_TYPE_DIR_MAP

    project = session.get(Project, project_id)
    if not project:
        return {"checked": 0, "cleaned": 0, "discovered": 0, "errors": 0, "details": []}

    project_root = Path(project.root_path)
    assets = list(session.exec(select(Asset).where(Asset.project_id == project_id)).all())

    # ── 阶段 1：清理丢失文件的 DB 记录 ──────────────────────
    checked = 0
    cleaned = 0
    discovered = 0
    errors = 0
    details = []

    for asset in assets:
        checked += 1
        try:
            full_path = resolve_asset_path(project_root, asset.file_path)
            if not full_path.exists():
                delete_asset(session, asset.id, delete_file=False)
                cleaned += 1
                details.append({
                    "action": "cleaned",
                    "asset_id": asset.id,
                    "file_path": asset.file_path,
                    "file_name": asset.file_name,
                })
                logger.info(f"[sync] 已清理丢失文件的素材记录: {asset.id} ({asset.file_path})")
        except Exception as e:
            errors += 1
            logger.warning(f"[sync] 处理素材 {asset.id} 时出错: {e}")

    # ── 阶段 2：扫描磁盘，发现未注册的文件 ──────────────────
    # 构建 DB 中已有的文件路径集合（相对路径，统一用 / 分隔）
    existing_paths = set()
    for asset in session.exec(select(Asset).where(Asset.project_id == project_id)).all():
        existing_paths.add(asset.file_path.replace("\\", "/"))

    # 模块目录 → (target_type, Model) 映射
    module_map = {
        "角色": ("character", Character),
        "场景": ("scene", Scene),
        "道具": ("prop", Prop),
    }

    # 图片/视频扩展名
    image_exts = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".gif", ".tiff"}
    video_exts = {".mp4", ".webm", ".mov", ".mkv", ".avi"}

    # 扫描角色/场景/道具目录
    for module_dir_name, (target_type, Model) in module_map.items():
        module_path = project_root / module_dir_name
        if not module_path.is_dir():
            continue

        # 遍历实体目录（如 角色/张三/）
        for entity_dir in module_path.iterdir():
            if not entity_dir.is_dir():
                continue

            # 查找匹配的实体
            entity_name_dir = entity_dir.name
            entity = _find_entity_by_dirname(session, Model, project_id, entity_name_dir)
            if not entity:
                continue

            # 扫描 images/ 和 videos/ 子目录
            for sub_dir_name in ("images", "videos"):
                sub_dir = entity_dir / sub_dir_name
                if not sub_dir.is_dir():
                    continue

                for file_path in sub_dir.iterdir():
                    if not file_path.is_file():
                        continue
                    ext = file_path.suffix.lower()
                    if sub_dir_name == "images" and ext not in image_exts:
                        continue
                    if sub_dir_name == "videos" and ext not in video_exts:
                        continue

                    # 计算相对路径
                    try:
                        rel_path = str(file_path.relative_to(project_root.resolve())).replace("\\", "/")
                    except ValueError:
                        continue

                    # 已有记录则跳过
                    if rel_path in existing_paths:
                        continue

                    # 确定素材类型和分类
                    if sub_dir_name == "videos":
                        asset_type = "video"
                        category = "shot_video" if target_type == "shot" else target_type
                    else:
                        asset_type = "image"
                        category = target_type

                    # 创建 Asset 记录
                    try:
                        file_size = file_path.stat().st_size
                        mime_type = mimetypes.guess_type(file_path.name)[0]

                        new_asset = create_asset_record(
                            session=session,
                            project_id=project_id,
                            asset_type=asset_type,
                            category=category,
                            file_path=rel_path,
                            file_size=file_size,
                            mime_type=mime_type,
                            status="ready",
                            target_type=target_type,
                            target_id=entity.id,
                        )

                        # 回填到实体的主图（如果实体没有主图）
                        if asset_type == "image" and hasattr(entity, "image_asset_id") and not entity.image_asset_id:
                            entity.image_asset_id = new_asset.id
                            session.add(entity)
                            session.commit()

                        existing_paths.add(rel_path)
                        discovered += 1
                        details.append({
                            "action": "discovered",
                            "asset_id": new_asset.id,
                            "file_path": rel_path,
                            "file_name": file_path.name,
                            "target_type": target_type,
                            "target_id": entity.id,
                        })
                        logger.info(f"[sync] 发现新素材: {rel_path} → {target_type}/{entity.id}")
                    except Exception as e:
                        errors += 1
                        logger.warning(f"[sync] 创建素材记录失败 {file_path}: {e}")

    # 扫描分镜目录
    episode_path = project_root / "分镜"
    if episode_path.is_dir():
        for shot_dir in episode_path.iterdir():
            if not shot_dir.is_dir():
                continue

            # 解析目录名如 "第1集_S01" → 找到对应的 Shot
            shot = _find_shot_by_dirname(session, project_id, shot_dir.name)
            if not shot:
                continue

            for sub_dir_name in ("images", "videos"):
                sub_dir = shot_dir / sub_dir_name
                if not sub_dir.is_dir():
                    continue

                for file_path in sub_dir.iterdir():
                    if not file_path.is_file():
                        continue
                    ext = file_path.suffix.lower()
                    if sub_dir_name == "images" and ext not in image_exts:
                        continue
                    if sub_dir_name == "videos" and ext not in video_exts:
                        continue

                    try:
                        rel_path = str(file_path.relative_to(project_root.resolve())).replace("\\", "/")
                    except ValueError:
                        continue

                    if rel_path in existing_paths:
                        continue

                    # 根据文件名推断 target_type
                    fname_lower = file_path.stem.lower()
                    # 默认 asset_type 为 image，避免变量泄漏
                    asset_type = "image"
                    if "last" in fname_lower or "末帧" in fname_lower:
                        shot_target_type = "shot_last_frame"
                        category = "last_frame"
                    elif "video" in fname_lower or "视频" in fname_lower or sub_dir_name == "videos":
                        shot_target_type = "shot_video"
                        category = "shot_video"
                        asset_type = "video"
                    else:
                        shot_target_type = "shot_first_frame"
                        category = "first_frame"

                    if sub_dir_name == "images":
                        asset_type = "image"

                    try:
                        file_size = file_path.stat().st_size
                        mime_type = mimetypes.guess_type(file_path.name)[0]

                        new_asset = create_asset_record(
                            session=session,
                            project_id=project_id,
                            asset_type=asset_type,
                            category=category,
                            file_path=rel_path,
                            file_size=file_size,
                            mime_type=mime_type,
                            status="ready",
                            target_type=shot_target_type,
                            target_id=shot.id,
                        )

                        # 回填到分镜
                        if shot_target_type == "shot_first_frame" and not shot.first_frame_asset_id:
                            shot.first_frame_asset_id = new_asset.id
                            session.add(shot)
                            session.commit()
                        elif shot_target_type == "shot_last_frame" and not shot.last_frame_asset_id:
                            shot.last_frame_asset_id = new_asset.id
                            session.add(shot)
                            session.commit()
                        elif shot_target_type == "shot_video" and not shot.video_asset_id:
                            shot.video_asset_id = new_asset.id
                            session.add(shot)
                            session.commit()

                        existing_paths.add(rel_path)
                        discovered += 1
                        details.append({
                            "action": "discovered",
                            "asset_id": new_asset.id,
                            "file_path": rel_path,
                            "file_name": file_path.name,
                            "target_type": shot_target_type,
                            "target_id": shot.id,
                        })
                        logger.info(f"[sync] 发现新分镜素材: {rel_path} → {shot_target_type}/{shot.id}")
                    except Exception as e:
                        errors += 1
                        logger.warning(f"[sync] 创建分镜素材记录失败 {file_path}: {e}")

    logger.info(f"[sync] 项目 {project_id} 同步完成: checked={checked}, cleaned={cleaned}, discovered={discovered}, errors={errors}")
    return {
        "checked": checked,
        "cleaned": cleaned,
        "discovered": discovered,
        "errors": errors,
        "details": details,
    }


def _find_entity_by_dirname(session: Session, Model, project_id: str, dirname: str):
    """根据目录名查找实体（用 sanitize_name 匹配 name 字段）。"""
    from app.services.business_service import sanitize_name

    # 直接用 SQL LIKE 粗筛，再精确匹配
    # sanitize_name 只替换特殊字符，所以 dirname 中不会含 % 或 _
    entities = list(session.exec(
        select(Model).where(Model.project_id == project_id)
    ).all())

    for entity in entities:
        if hasattr(entity, "name") and entity.name:
            if sanitize_name(entity.name) == dirname:
                return entity
    return None


def _find_shot_by_dirname(session: Session, project_id: str, dirname: str):
    """根据目录名如 '第1集_S01' 查找 Shot。"""
    from app.models import Shot, Episode

    # 尝试解析 "第N集_Sxx" 或 "第N集_Mxx" 格式
    m = re.match(r"第(\d+)集[_\s](.+)", dirname)
    if not m:
        return None

    ep_no = int(m.group(1))
    shot_no_str = m.group(2)

    # 查找剧集
    episode = session.exec(
        select(Episode).where(
            Episode.project_id == project_id,
            Episode.episode_no == ep_no,
        )
    ).first()

    if not episode:
        return None

    # 查找分镜（shot_no 可能是 "S01" 或数字）
    shot_no_num = None
    num_match = re.search(r"\d+", shot_no_str)
    if num_match:
        shot_no_num = int(num_match.group())

    if shot_no_num is not None:
        shot = session.exec(
            select(Shot).where(
                Shot.episode_id == episode.id,
                Shot.shot_no == shot_no_num,
            )
        ).first()
        return shot

    return None
