"""画风预置服务。

提供画风预置的增删改查、默认预置管理、内置预置初始化。
"""

from __future__ import annotations

import logging
from typing import Optional

from sqlmodel import Session, select

from app.models.style_preset import StylePreset
from app.schemas.style_preset import StylePresetCreate, StylePresetUpdate

logger = logging.getLogger(__name__)


# ============================================================
# 内置画风预置
# ============================================================

BUILTIN_STYLE_PRESETS: list[dict] = [
    {
        "title": "二次元动漫",
        "description": "二次元动漫风格，精致细腻的日系动画画风，柔和色彩，清晰线条，高饱和度",
        "is_default": True,
        "sort_order": 0,
    },
    {
        "title": "3D渲染",
        "description": "3D渲染风格，次世代3D建模质感，逼真光影，细腻材质纹理，虚幻引擎级画质",
        "is_default": False,
        "sort_order": 10,
    },
    {
        "title": "水墨插画",
        "description": "水墨插画风格，传统中国水墨画意境，留白构图，晕染笔触，淡雅色调",
        "is_default": False,
        "sort_order": 20,
    },
    {
        "title": "写实摄影",
        "description": "写实摄影，真实感影像，电影级画质，8K超高清，自然光影，极致细节纹理",
        "is_default": False,
        "sort_order": 30,
    },
    {
        "title": "电影感",
        "description": "电影级写实质感，柔和电影光影，自然景深虚化，极致细节纹理，丰富色彩层次，8K超高清",
        "is_default": False,
        "sort_order": 40,
    },
    {
        "title": "漫画",
        "description": "漫画风格，黑白漫画线条，网点阴影，夸张表情，分镜构图感",
        "is_default": False,
        "sort_order": 50,
    },
]


# ============================================================
# 通用 CRUD
# ============================================================

def list_presets(session: Session) -> list[StylePreset]:
    """查询所有画风预置，按 sort_order 排序。"""
    stmt = select(StylePreset).order_by(StylePreset.sort_order, StylePreset.created_at)
    return list(session.exec(stmt).all())


def get_preset(session: Session, preset_id: str) -> Optional[StylePreset]:
    """获取单个画风预置。"""
    return session.get(StylePreset, preset_id)


def get_default_preset(session: Session) -> Optional[StylePreset]:
    """获取默认画风预置。"""
    return session.exec(
        select(StylePreset)
        .where(StylePreset.is_default == True)
        .order_by(StylePreset.sort_order)
    ).first()


def get_preset_by_title(session: Session, title: str) -> Optional[StylePreset]:
    """按标题查找画风预置。"""
    return session.exec(
        select(StylePreset).where(StylePreset.title == title)
    ).first()


def _clear_default_flag(session: Session, exclude_id: Optional[str] = None) -> None:
    """取消其他预置的默认标记。"""
    stmt = select(StylePreset).where(StylePreset.is_default == True)
    if exclude_id:
        stmt = stmt.where(StylePreset.id != exclude_id)
    for preset in session.exec(stmt).all():
        preset.is_default = False
        session.add(preset)


def create_preset(session: Session, data: StylePresetCreate) -> StylePreset:
    """创建画风预置。"""
    preset = StylePreset(**data.model_dump())
    if preset.is_default:
        _clear_default_flag(session)
    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def update_preset(
    session: Session,
    preset_id: str,
    data: StylePresetUpdate,
) -> Optional[StylePreset]:
    """更新画风预置。所有字段均可修改。"""
    preset = session.get(StylePreset, preset_id)
    if not preset:
        return None

    updates = data.model_dump(exclude_unset=True)

    for key, value in updates.items():
        setattr(preset, key, value)

    if preset.is_default:
        _clear_default_flag(session, exclude_id=preset.id)

    session.add(preset)
    session.commit()
    session.refresh(preset)
    return preset


def delete_preset(session: Session, preset_id: str) -> bool:
    """删除画风预置。"""
    preset = session.get(StylePreset, preset_id)
    if not preset:
        return False
    session.delete(preset)
    session.commit()
    return True


def reorder_presets(session: Session, ordered_ids: list[str]) -> None:
    """按给定 ID 顺序批量更新 sort_order。"""
    for idx, preset_id in enumerate(ordered_ids):
        preset = session.get(StylePreset, preset_id)
        if preset:
            preset.sort_order = idx * 10
            session.add(preset)
    session.commit()


# ============================================================
# 初始化内置预置
# ============================================================

def seed_builtin_presets(session: Session) -> int:
    """初始化内置画风预置。已存在同名内置预置则跳过。

    同时清理已废弃的"默认"预置（title="默认" 且 description="通用"）。

    返回新增数量。
    """
    # 清理废弃的"默认"预置
    deprecated = session.exec(
        select(StylePreset).where(StylePreset.title == "默认").where(StylePreset.description == "通用")
    ).first()
    if deprecated:
        session.delete(deprecated)
        session.commit()
        logger.info("[style_presets] 已清理废弃的「默认」画风预置")

    added = 0
    for data in BUILTIN_STYLE_PRESETS:
        exists = session.exec(
            select(StylePreset).where(StylePreset.is_builtin == True).where(StylePreset.title == data["title"])
        ).first()
        if exists:
            continue

        has_any = session.exec(select(StylePreset)).first()
        preset = StylePreset(
            title=data["title"],
            description=data["description"],
            is_default=not has_any and data.get("is_default", False),
            is_builtin=True,
            sort_order=data["sort_order"],
        )
        session.add(preset)
        added += 1

    if added:
        session.commit()
        logger.info(f"[style_presets] 已初始化 {added} 个内置画风预置")
    return added
