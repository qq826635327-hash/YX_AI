"""分镜关联引用服务。"""

from __future__ import annotations

from typing import List, Optional

from sqlmodel import Session, func, select

from app.models import Character, Prop, Scene
from app.models.shot_reference import ShotCharacter, ShotProp, ShotScene


# ============================================================
# 关联管理
# ============================================================

def add_characters(session: Session, shot_id: str, character_ids: list[str]) -> list[ShotCharacter]:
    # 计算已有记录数作为 sort_order 起点，避免覆盖既有顺序
    existing_count = session.exec(
        select(func.count()).where(ShotCharacter.shot_id == shot_id)
    ).one()
    results = []
    next_order = existing_count
    for cid in character_ids:
        existing = session.get(ShotCharacter, (shot_id, cid))
        if not existing:
            ref = ShotCharacter(shot_id=shot_id, character_id=cid, sort_order=next_order)
            session.add(ref)
            results.append(ref)
            next_order += 1
    session.commit()
    for r in results:
        session.refresh(r)
    return results


def remove_character(session: Session, shot_id: str, character_id: str) -> bool:
    ref = session.get(ShotCharacter, (shot_id, character_id))
    if not ref:
        return False
    session.delete(ref)
    session.commit()
    return True


def add_scenes(session: Session, shot_id: str, scene_ids: list[str]) -> list[ShotScene]:
    existing_count = session.exec(
        select(func.count()).where(ShotScene.shot_id == shot_id)
    ).one()
    results = []
    next_order = existing_count
    for sid in scene_ids:
        existing = session.get(ShotScene, (shot_id, sid))
        if not existing:
            ref = ShotScene(shot_id=shot_id, scene_id=sid, sort_order=next_order)
            session.add(ref)
            results.append(ref)
            next_order += 1
    session.commit()
    for r in results:
        session.refresh(r)
    return results


def remove_scene(session: Session, shot_id: str, scene_id: str) -> bool:
    ref = session.get(ShotScene, (shot_id, scene_id))
    if not ref:
        return False
    session.delete(ref)
    session.commit()
    return True


def add_props(session: Session, shot_id: str, prop_ids: list[str]) -> list[ShotProp]:
    existing_count = session.exec(
        select(func.count()).where(ShotProp.shot_id == shot_id)
    ).one()
    results = []
    next_order = existing_count
    for pid in prop_ids:
        existing = session.get(ShotProp, (shot_id, pid))
        if not existing:
            ref = ShotProp(shot_id=shot_id, prop_id=pid, sort_order=next_order)
            session.add(ref)
            results.append(ref)
            next_order += 1
    session.commit()
    for r in results:
        session.refresh(r)
    return results


def remove_prop(session: Session, shot_id: str, prop_id: str) -> bool:
    ref = session.get(ShotProp, (shot_id, prop_id))
    if not ref:
        return False
    session.delete(ref)
    session.commit()
    return True


# ============================================================
# 查询
# ============================================================

def get_shot_characters(session: Session, shot_id: str) -> List[Character]:
    stmt = (
        select(Character)
        .join(ShotCharacter, ShotCharacter.character_id == Character.id)
        .where(ShotCharacter.shot_id == shot_id)
        .order_by(ShotCharacter.sort_order)
    )
    return list(session.exec(stmt).all())


def get_shot_scenes(session: Session, shot_id: str) -> List[Scene]:
    stmt = (
        select(Scene)
        .join(ShotScene, ShotScene.scene_id == Scene.id)
        .where(ShotScene.shot_id == shot_id)
        .order_by(ShotScene.sort_order)
    )
    return list(session.exec(stmt).all())


def get_shot_props(session: Session, shot_id: str) -> List[Prop]:
    stmt = (
        select(Prop)
        .join(ShotProp, ShotProp.prop_id == Prop.id)
        .where(ShotProp.shot_id == shot_id)
        .order_by(ShotProp.sort_order)
    )
    return list(session.exec(stmt).all())


def get_shot_references(session: Session, shot_id: str) -> dict:
    """获取分镜的所有关联实体，并收集已生成的参考图 ID。"""
    characters = get_shot_characters(session, shot_id)
    scenes = get_shot_scenes(session, shot_id)
    props = get_shot_props(session, shot_id)

    reference_image_ids = []
    for char in characters:
        if char.image_asset_id and char.gen_status == "ready":
            reference_image_ids.append(char.image_asset_id)
    for scene in scenes:
        if scene.image_asset_id and scene.gen_status == "ready":
            reference_image_ids.append(scene.image_asset_id)
    for prop in props:
        if prop.image_asset_id and prop.gen_status == "ready":
            reference_image_ids.append(prop.image_asset_id)

    def _entity_to_dict(e):
        return {
            "id": e.id,
            "name": e.name,
            "image_asset_id": e.image_asset_id,
            "gen_status": e.gen_status,
        }

    return {
        "characters": [_entity_to_dict(c) for c in characters],
        "scenes": [_entity_to_dict(s) for s in scenes],
        "props": [_entity_to_dict(p) for p in props],
        "reference_image_ids": reference_image_ids,
    }


def collect_reference_prompts(session: Session, shot_id: str) -> str:
    """收集关联实体的 settings 描述，拼接为参考 Prompt。"""
    parts = []
    characters = get_shot_characters(session, shot_id)
    scenes = get_shot_scenes(session, shot_id)
    props = get_shot_props(session, shot_id)

    if characters:
        char_settings = [c.settings or c.description or c.name for c in characters]
        parts.append("角色参考: " + "; ".join(char_settings))
    if scenes:
        scene_settings = [s.settings or s.description or s.name for s in scenes]
        parts.append("场景参考: " + "; ".join(scene_settings))
    if props:
        prop_settings = [p.settings or p.description or p.name for p in props]
        parts.append("道具参考: " + "; ".join(prop_settings))

    return "\n".join(parts)
