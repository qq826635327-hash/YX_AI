"""剧本服务：剧本文档管理 + 解析管线入口。"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Session, select

from app.models import ScriptDocument
from app.schemas.script import ScriptUpdate

logger = logging.getLogger(__name__)


def get_script(session: Session, project_id: str) -> Optional[ScriptDocument]:
    """获取项目最新版剧本。"""
    stmt = (
        select(ScriptDocument)
        .where(ScriptDocument.project_id == project_id)
        .order_by(ScriptDocument.version.desc())
    )
    return session.exec(stmt).first()


def update_script(session: Session, project_id: str, payload: ScriptUpdate) -> ScriptDocument:
    """更新剧本文本（自动版本递增）。"""
    existing = get_script(session, project_id)
    if existing:
        # 新建一版
        new_version = existing.version + 1
        doc = ScriptDocument(
            project_id=project_id,
            raw_text=payload.raw_text,
            version=new_version,
            parse_status=existing.parse_status,
            parsed_result=existing.parsed_result,
        )
    else:
        doc = ScriptDocument(
            project_id=project_id,
            raw_text=payload.raw_text,
            version=1,
        )
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def save_parsed_result(session: Session, script_id: str, parsed: dict) -> Optional[ScriptDocument]:
    """保存解析结果。"""
    doc = session.get(ScriptDocument, script_id)
    if not doc:
        return None
    doc.parsed_result = parsed
    doc.parse_status = "parsed"
    doc.parse_error = None
    doc.parsed_at = datetime.now(timezone.utc).isoformat()
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def mark_parsing(session: Session, script_id: str) -> Optional[ScriptDocument]:
    """标记为解析中。"""
    doc = session.get(ScriptDocument, script_id)
    if not doc:
        return None
    doc.parse_status = "parsing"
    doc.parse_error = None
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def mark_parse_failed(session: Session, script_id: str, error: str) -> Optional[ScriptDocument]:
    """标记解析失败。"""
    doc = session.get(ScriptDocument, script_id)
    if not doc:
        return None
    doc.parse_status = "failed"
    doc.parse_error = error
    session.add(doc)
    session.commit()
    session.refresh(doc)
    return doc


def write_parsed_to_db(session: Session, project_id: str, parsed: dict) -> dict:
    """将解析结果写入业务表（角色/场景/道具/剧集/分镜）。

    Returns:
        写入统计：{characters, scenes, props, episodes, shots}
    """
    from sqlalchemy import delete as sa_delete
    from app.models import Character, Episode, Prop, Scene, Shot
    from app.models import ShotCharacter, ShotScene, ShotProp
    from app.services.project_service import update_project_stats

    # 清空旧数据（重新解析）——批量删除，避免 N+1 查询
    # 1. 收集所有旧 shot_ids
    old_episode_ids = list(session.exec(
        select(Episode.id).where(Episode.project_id == project_id)
    ).all())
    old_shot_ids: list = []
    if old_episode_ids:
        old_shot_ids = list(session.exec(
            select(Shot.id).where(Shot.episode_id.in_(old_episode_ids))
        ).all())

    # 2. 批量删除分镜关联表（多对多）
    if old_shot_ids:
        session.exec(sa_delete(ShotCharacter).where(ShotCharacter.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(ShotScene).where(ShotScene.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(ShotProp).where(ShotProp.shot_id.in_(old_shot_ids)))
        # 3. 批量删除分镜
        session.exec(sa_delete(Shot).where(Shot.id.in_(old_shot_ids)))

    # 4. 批量删除剧集
    if old_episode_ids:
        session.exec(sa_delete(Episode).where(Episode.id.in_(old_episode_ids)))

    # 5. 批量删除角色/场景/道具
    for model in (Character, Scene, Prop):
        session.exec(sa_delete(model).where(model.project_id == project_id))
    # 不在此处 commit，与写入新数据在同一事务中，失败可整体回滚

    # 写入角色
    char_count = 0
    for c in parsed.get("characters", []):
        char = Character(
            project_id=project_id,
            name=c.get("name") or "未命名",
            char_type=c.get("char_type") or "supporting",
            description=c.get("description"),
            settings=c.get("settings"),
        )
        session.add(char)
        char_count += 1

    # 写入场景
    scene_count = 0
    for s in parsed.get("scenes", []):
        scene = Scene(
            project_id=project_id,
            name=s.get("name") or "未命名",
            description=s.get("description"),
            settings=s.get("settings"),
        )
        session.add(scene)
        scene_count += 1

    # 写入道具
    prop_count = 0
    for p in parsed.get("props", []):
        prop = Prop(
            project_id=project_id,
            name=p.get("name") or "未命名",
            description=p.get("description"),
            settings=p.get("settings"),
        )
        session.add(prop)
        prop_count += 1

    # 写入剧集与分镜
    ep_count = 0
    shot_count = 0
    for ep in parsed.get("episodes", []):
        episode = Episode(
            project_id=project_id,
            episode_no=ep.get("episode_no") or (ep_count + 1),
            title=ep.get("title") or f"第{ep_count + 1}集",
            summary=ep.get("summary"),
            sort_order=ep_count,
        )
        session.add(episode)
        session.flush()  # 拿到 id
        ep_count += 1

        for sh in ep.get("shots", []):
            shot = Shot(
                episode_id=episode.id,
                project_id=project_id,
                shot_no=sh.get("shot_no") or (shot_count + 1),
                summary=sh.get("summary"),
                first_frame_prompt=sh.get("first_frame_prompt"),
                last_frame_prompt=sh.get("last_frame_prompt"),
                video_prompt=sh.get("video_prompt"),
                sort_order=shot_count,
            )
            session.add(shot)
            shot_count += 1

    session.commit()

    # 更新项目统计
    update_project_stats(session, project_id)

    return {
        "characters": char_count,
        "scenes": scene_count,
        "props": prop_count,
        "episodes": ep_count,
        "shots": shot_count,
    }
