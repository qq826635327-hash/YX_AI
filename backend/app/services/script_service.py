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


def save_pre_parse_snapshot(session: Session, project_id: str, script_id: str) -> None:
    """解析前保存当前实体快照，用于取消时恢复。"""
    from app.models import Character, Scene, Prop, Episode, Shot
    from app.core.serialization import serialize_models

    snapshot: dict = {}

    # 保存角色
    chars = session.exec(select(Character).where(Character.project_id == project_id)).all()
    snapshot["characters"] = serialize_models(chars)

    # 保存场景
    scenes = session.exec(select(Scene).where(Scene.project_id == project_id)).all()
    snapshot["scenes"] = serialize_models(scenes)

    # 保存道具
    props = session.exec(select(Prop).where(Prop.project_id == project_id)).all()
    snapshot["props"] = serialize_models(props)

    # 保存剧集
    episodes = session.exec(select(Episode).where(Episode.project_id == project_id)).all()
    snapshot["episodes"] = serialize_models(episodes)

    # 保存分镜
    shots = session.exec(select(Shot).where(Shot.project_id == project_id)).all()
    snapshot["shots"] = serialize_models(shots)

    # 保存到 ScriptDocument
    doc = session.get(ScriptDocument, script_id)
    if doc:
        doc.pre_parse_snapshot = snapshot
        session.add(doc)
        session.commit()
        logger.info(f"已保存解析前快照: 角色={len(chars)}, 场景={len(scenes)}, 道具={len(props)}, 剧集={len(episodes)}, 分镜={len(shots)}")


def restore_from_snapshot(session: Session, project_id: str, script_id: str) -> bool:
    """从解析前快照恢复数据（取消解析时调用）。

    Returns:
        True 恢复成功，False 无快照可恢复
    """
    from sqlalchemy import delete as sa_delete
    from app.models import Character, Scene, Prop, Episode, Shot
    from app.models import ShotCharacter, ShotScene, ShotProp
    from app.services.business_service import ensure_entity_dir
    from app.services.project_service import update_project_stats

    doc = session.get(ScriptDocument, script_id)
    if not doc or not doc.pre_parse_snapshot:
        logger.warning(f"无解析前快照可恢复 (script_id={script_id})")
        return False

    snapshot = doc.pre_parse_snapshot

    # 删除当前所有实体
    old_episode_ids = list(session.exec(select(Episode.id).where(Episode.project_id == project_id)).all())
    old_shot_ids: list = []
    if old_episode_ids:
        old_shot_ids = list(session.exec(select(Shot.id).where(Shot.episode_id.in_(old_episode_ids))).all())
    if old_shot_ids:
        session.exec(sa_delete(ShotCharacter).where(ShotCharacter.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(ShotScene).where(ShotScene.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(ShotProp).where(ShotProp.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(Shot).where(Shot.id.in_(old_shot_ids)))
    if old_episode_ids:
        session.exec(sa_delete(Episode).where(Episode.id.in_(old_episode_ids)))
    session.exec(sa_delete(Character).where(Character.project_id == project_id))
    session.exec(sa_delete(Scene).where(Scene.project_id == project_id))
    session.exec(sa_delete(Prop).where(Prop.project_id == project_id))

    # 从快照恢复角色
    for c_data in snapshot.get("characters", []):
        char = Character(
            project_id=project_id,
            name=c_data.get("name", "未命名"),
            gender=c_data.get("gender"),
            age=c_data.get("age"),
            char_type=c_data.get("char_type", "supporting"),
            description=c_data.get("description"),
            settings=c_data.get("settings"),
        )
        session.add(char)

    # 从快照恢复场景
    for s_data in snapshot.get("scenes", []):
        scene = Scene(
            project_id=project_id,
            name=s_data.get("name", "未命名"),
            description=s_data.get("description"),
            settings=s_data.get("settings"),
            camera_hint=s_data.get("camera_hint"),
        )
        session.add(scene)

    # 从快照恢复道具
    for p_data in snapshot.get("props", []):
        prop = Prop(
            project_id=project_id,
            name=p_data.get("name", "未命名"),
            description=p_data.get("description"),
            settings=p_data.get("settings"),
        )
        session.add(prop)

    # 从快照恢复剧集和分镜
    ep_id_map: dict[str, str] = {}  # old_id -> new_id
    for ep_data in snapshot.get("episodes", []):
        episode = Episode(
            project_id=project_id,
            episode_no=ep_data.get("episode_no", 1),
            title=ep_data.get("title", "第1集"),
            summary=ep_data.get("summary"),
            sort_order=ep_data.get("sort_order", 0),
        )
        session.add(episode)
        session.flush()
        old_ep_id = ep_data.get("id")
        if old_ep_id:
            ep_id_map[old_ep_id] = episode.id

    for sh_data in snapshot.get("shots", []):
        old_ep_id = sh_data.get("episode_id")
        new_ep_id = ep_id_map.get(old_ep_id) if old_ep_id else None
        if not new_ep_id:
            continue
        shot = Shot(
            episode_id=new_ep_id,
            project_id=project_id,
            shot_no=sh_data.get("shot_no", 1),
            summary=sh_data.get("summary"),
            first_frame_prompt=sh_data.get("first_frame_prompt"),
            last_frame_prompt=sh_data.get("last_frame_prompt"),
            video_prompt=sh_data.get("video_prompt"),
            camera_size=sh_data.get("camera_size"),
            camera_angle=sh_data.get("camera_angle"),
            camera_movement=sh_data.get("camera_movement"),
            sort_order=sh_data.get("sort_order", 0),
        )
        session.add(shot)

    session.commit()

    # 同步创建磁盘目录
    for char in session.exec(select(Character).where(Character.project_id == project_id)).all():
        ensure_entity_dir(session, Character, char, project_id)
    for scene in session.exec(select(Scene).where(Scene.project_id == project_id)).all():
        ensure_entity_dir(session, Scene, scene, project_id)
    for prop in session.exec(select(Prop).where(Prop.project_id == project_id)).all():
        ensure_entity_dir(session, Prop, prop, project_id)

    update_project_stats(session, project_id)

    # 清除快照，标记状态
    doc.parse_status = "none"
    doc.parse_error = None
    doc.pre_parse_snapshot = None
    session.add(doc)
    session.commit()

    logger.info(f"已从快照恢复数据 (project_id={project_id})")
    return True


def write_entities_to_db(session: Session, project_id: str, characters: list, scenes: list, props: list, preserve_prompts: bool = False, targets: set[str] | None = None) -> dict:
    """将角色/场景/道具写入业务表并同步创建磁盘目录。

    在剧本解析的「提取角色/场景/道具」阶段完成后立即调用，
    让前端可以尽早看到实体数据。

    Args:
        targets: 解析目标集合，仅包含 "characters"/"scenes"/"props" 时才删除并写入对应实体。
                 为 None 时全部写入（向后兼容）。

    Returns:
        写入统计：{characters, scenes, props}
    """
    from sqlalchemy import delete as sa_delete
    from app.models import Character, Prop, Scene
    from app.services.business_service import ensure_entity_dir
    from app.services.project_service import update_project_stats

    if targets is None:
        targets = {"characters", "scenes", "props"}

    # 如果 preserve_prompts，先收集旧实体的提示词映射
    old_char_prompts: dict[str, str] = {}
    old_scene_prompts: dict[str, str] = {}
    old_prop_prompts: dict[str, str] = {}

    if preserve_prompts:
        if "characters" in targets:
            for c in session.exec(select(Character).where(Character.project_id == project_id)).all():
                if c.settings:
                    old_char_prompts[c.name] = c.settings
        if "scenes" in targets:
            for s in session.exec(select(Scene).where(Scene.project_id == project_id)).all():
                if s.settings:
                    old_scene_prompts[s.name] = s.settings
        if "props" in targets:
            for p in session.exec(select(Prop).where(Prop.project_id == project_id)).all():
                if p.settings:
                    old_prop_prompts[p.name] = p.settings
        logger.info(f"保留提示词模式：收集到 角色={len(old_char_prompts)}, 场景={len(old_scene_prompts)}, 道具={len(old_prop_prompts)} 条旧提示词")

    # 仅清空本次要写入的实体类型
    if "characters" in targets:
        session.exec(sa_delete(Character).where(Character.project_id == project_id))
    if "scenes" in targets:
        session.exec(sa_delete(Scene).where(Scene.project_id == project_id))
    if "props" in targets:
        session.exec(sa_delete(Prop).where(Prop.project_id == project_id))

    # 写入角色
    char_count = 0
    for c in characters:
        char_type = c.get("char_type", "supporting")
        role_map = {"主角": "protagonist", "配角": "supporting", "群演": "extra"}
        char_type = role_map.get(char_type, char_type)

        char_name = c.get("name") or "未命名"
        char_settings = c.get("settings")
        if preserve_prompts and char_name in old_char_prompts:
            char_settings = old_char_prompts[char_name]

        char = Character(
            project_id=project_id,
            name=char_name,
            gender=c.get("gender"),
            age=c.get("age"),
            char_type=char_type or "supporting",
            description=c.get("description"),
            settings=char_settings,
        )
        session.add(char)
        char_count += 1

    # 写入场景
    scene_count = 0
    for s in scenes:
        scene_name = s.get("name") or "未命名"
        scene_settings = s.get("settings")
        if preserve_prompts and scene_name in old_scene_prompts:
            scene_settings = old_scene_prompts[scene_name]

        scene = Scene(
            project_id=project_id,
            name=scene_name,
            description=s.get("description"),
            settings=scene_settings,
            camera_hint=s.get("camera_hint"),
        )
        session.add(scene)
        scene_count += 1

    # 写入道具
    prop_count = 0
    for p in props:
        prop_name = p.get("name") or "未命名"
        prop_settings = p.get("settings")
        if preserve_prompts and prop_name in old_prop_prompts:
            prop_settings = old_prop_prompts[prop_name]

        prop = Prop(
            project_id=project_id,
            name=prop_name,
            description=p.get("description"),
            settings=prop_settings,
        )
        session.add(prop)
        prop_count += 1

    session.commit()

    # 同步创建磁盘目录
    for char in session.exec(select(Character).where(Character.project_id == project_id)).all():
        ensure_entity_dir(session, Character, char, project_id)
    for scene in session.exec(select(Scene).where(Scene.project_id == project_id)).all():
        ensure_entity_dir(session, Scene, scene, project_id)
    for prop in session.exec(select(Prop).where(Prop.project_id == project_id)).all():
        ensure_entity_dir(session, Prop, prop, project_id)

    update_project_stats(session, project_id)

    return {"characters": char_count, "scenes": scene_count, "props": prop_count}


def write_episodes_to_db(session: Session, project_id: str, episodes: list, preserve_prompts: bool = False, skip_if_empty: bool = False) -> dict:
    """将剧集与分镜写入业务表并同步创建磁盘目录。

    在剧本解析的「分镜拆分」阶段完成后调用。

    Args:
        skip_if_empty: 为 True 且 episodes 为空时，跳过写入（不删除旧数据）。
            用于 parse_targets 未勾选 episodes 的场景。

    Returns:
        写入统计：{episodes, shots}
    """
    from sqlalchemy import delete as sa_delete
    from app.models import Character, Episode, Prop, Scene, Shot
    from app.models import ShotCharacter, ShotScene, ShotProp
    from app.services.business_service import ensure_entity_dir
    from app.services.project_service import update_project_stats

    # 如果 skip_if_empty 且没有新剧集，跳过写入（保留旧数据）
    if skip_if_empty and not episodes:
        return {"episodes": 0, "shots": 0}

    # 如果 preserve_prompts，先收集旧分镜的提示词映射
    old_shot_prompts: dict[int, dict] = {}
    if preserve_prompts:
        for sh in session.exec(select(Shot).where(Shot.project_id == project_id)).all():
            prompts = {}
            if sh.first_frame_prompt:
                prompts["first_frame_prompt"] = sh.first_frame_prompt
            if sh.last_frame_prompt:
                prompts["last_frame_prompt"] = sh.last_frame_prompt
            if sh.video_prompt:
                prompts["video_prompt"] = sh.video_prompt
            if prompts:
                old_shot_prompts[sh.shot_no] = prompts
        logger.info(f"保留提示词模式：收集到 分镜={len(old_shot_prompts)} 条旧提示词")

    # 清空旧的剧集和分镜
    old_episode_ids = list(session.exec(
        select(Episode.id).where(Episode.project_id == project_id)
    ).all())
    old_shot_ids: list = []
    if old_episode_ids:
        old_shot_ids = list(session.exec(
            select(Shot.id).where(Shot.episode_id.in_(old_episode_ids))
        ).all())

    if old_shot_ids:
        session.exec(sa_delete(ShotCharacter).where(ShotCharacter.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(ShotScene).where(ShotScene.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(ShotProp).where(ShotProp.shot_id.in_(old_shot_ids)))
        session.exec(sa_delete(Shot).where(Shot.id.in_(old_shot_ids)))
    if old_episode_ids:
        session.exec(sa_delete(Episode).where(Episode.id.in_(old_episode_ids)))

    # 预加载项目内实体名 -> ID 映射，用于匹配分镜关联
    char_name_to_id = {
        c.name: c.id
        for c in session.exec(select(Character).where(Character.project_id == project_id)).all()
    }
    scene_name_to_id = {
        s.name: s.id
        for s in session.exec(select(Scene).where(Scene.project_id == project_id)).all()
    }
    prop_name_to_id = {
        p.name: p.id
        for p in session.exec(select(Prop).where(Prop.project_id == project_id)).all()
    }

    # 写入剧集与分镜
    ep_count = 0
    shot_count = 0
    for ep in episodes:
        episode = Episode(
            project_id=project_id,
            episode_no=ep.get("episode_no") or (ep_count + 1),
            title=ep.get("title") or f"第{ep_count + 1}集",
            summary=ep.get("summary"),
            sort_order=ep_count,
        )
        session.add(episode)
        session.flush()
        ep_count += 1

        for sh in ep.get("shots", []):
            shot_no = sh.get("shot_no") or (shot_count + 1)
            ff_prompt = sh.get("first_frame_prompt")
            lf_prompt = sh.get("last_frame_prompt")
            v_prompt = sh.get("video_prompt")
            if preserve_prompts and shot_no in old_shot_prompts:
                old_p = old_shot_prompts[shot_no]
                if "first_frame_prompt" in old_p:
                    ff_prompt = old_p["first_frame_prompt"]
                if "last_frame_prompt" in old_p:
                    lf_prompt = old_p["last_frame_prompt"]
                if "video_prompt" in old_p:
                    v_prompt = old_p["video_prompt"]

            shot = Shot(
                episode_id=episode.id,
                project_id=project_id,
                shot_no=shot_no,
                summary=sh.get("summary"),
                first_frame_prompt=ff_prompt,
                last_frame_prompt=lf_prompt,
                video_prompt=v_prompt,
                camera_size=sh.get("camera_size"),
                camera_angle=sh.get("camera_angle"),
                camera_movement=sh.get("camera_movement"),
                sort_order=shot_count,
            )
            session.add(shot)
            session.flush()  # 拿到 shot.id 后才能写关联表
            shot_count += 1

            # 建立分镜与角色/场景/道具的关联（图生图 reference 用）
            _bind_shot_entities(
                session, shot,
                sh.get("character_names", []),
                sh.get("scene_names", []),
                sh.get("prop_names", []),
                char_name_to_id, scene_name_to_id, prop_name_to_id,
            )

    session.commit()

    # 同步创建磁盘目录
    for shot in session.exec(select(Shot).where(Shot.project_id == project_id)).all():
        ensure_entity_dir(session, Shot, shot, project_id)

    update_project_stats(session, project_id)

    return {"episodes": ep_count, "shots": shot_count}


def write_parsed_to_db(session: Session, project_id: str, parsed: dict, preserve_prompts: bool = False) -> dict:
    """将解析结果写入业务表（角色/场景/道具/剧集/分镜），并同步创建磁盘目录。

    Args:
        preserve_prompts: 为 True 时，已有实体的提示词（settings）不会被新解析结果覆盖。
            实现方式：先收集旧实体名→提示词映射，删除旧数据后写入新数据时，
            如果旧实体同名且已有提示词，则保留旧提示词。

    Returns:
        写入统计：{characters, scenes, props, episodes, shots}
    """
    from sqlalchemy import delete as sa_delete
    from app.models import Character, Episode, Prop, Scene, Shot
    from app.models import ShotCharacter, ShotScene, ShotProp
    from app.services.business_service import ensure_entity_dir, MODULE_DIR_MAP
    from app.services.project_service import update_project_stats

    # 如果 preserve_prompts，先收集旧实体的提示词映射
    old_char_prompts: dict[str, str] = {}
    old_scene_prompts: dict[str, str] = {}
    old_prop_prompts: dict[str, str] = {}
    old_shot_prompts: dict[str, dict] = {}  # shot_no -> {first_frame, last_frame, video}

    if preserve_prompts:
        for c in session.exec(select(Character).where(Character.project_id == project_id)).all():
            if c.settings:
                old_char_prompts[c.name] = c.settings
        for s in session.exec(select(Scene).where(Scene.project_id == project_id)).all():
            if s.settings:
                old_scene_prompts[s.name] = s.settings
        for p in session.exec(select(Prop).where(Prop.project_id == project_id)).all():
            if p.settings:
                old_prop_prompts[p.name] = p.settings
        for sh in session.exec(select(Shot).where(Shot.project_id == project_id)).all():
            prompts = {}
            if sh.first_frame_prompt:
                prompts["first_frame_prompt"] = sh.first_frame_prompt
            if sh.last_frame_prompt:
                prompts["last_frame_prompt"] = sh.last_frame_prompt
            if sh.video_prompt:
                prompts["video_prompt"] = sh.video_prompt
            if prompts:
                old_shot_prompts[sh.shot_no] = prompts
        logger.info(f"保留提示词模式：收集到 角色={len(old_char_prompts)}, 场景={len(old_scene_prompts)}, 道具={len(old_prop_prompts)}, 分镜={len(old_shot_prompts)} 条旧提示词")

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
        char_type = c.get("char_type", "supporting")
        # 兼容模板中的中文 role 字段
        role_map = {"主角": "protagonist", "配角": "supporting", "群演": "extra"}
        char_type = role_map.get(char_type, char_type)

        char_name = c.get("name") or "未命名"
        # 保留已有提示词：如果旧实体同名且有提示词，则不覆盖
        char_settings = c.get("settings")
        if preserve_prompts and char_name in old_char_prompts:
            char_settings = old_char_prompts[char_name]

        char = Character(
            project_id=project_id,
            name=char_name,
            gender=c.get("gender"),
            age=c.get("age"),
            char_type=char_type or "supporting",
            description=c.get("description"),
            settings=char_settings,
        )
        session.add(char)
        char_count += 1

    # 写入场景
    scene_count = 0
    for s in parsed.get("scenes", []):
        scene_name = s.get("name") or "未命名"
        scene_settings = s.get("settings")
        if preserve_prompts and scene_name in old_scene_prompts:
            scene_settings = old_scene_prompts[scene_name]

        scene = Scene(
            project_id=project_id,
            name=scene_name,
            description=s.get("description"),
            settings=scene_settings,
            camera_hint=s.get("camera_hint"),
        )
        session.add(scene)
        scene_count += 1

    # 写入道具
    prop_count = 0
    for p in parsed.get("props", []):
        prop_name = p.get("name") or "未命名"
        prop_settings = p.get("settings")
        if preserve_prompts and prop_name in old_prop_prompts:
            prop_settings = old_prop_prompts[prop_name]

        prop = Prop(
            project_id=project_id,
            name=prop_name,
            description=p.get("description"),
            settings=prop_settings,
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
            shot_no = sh.get("shot_no") or (shot_count + 1)
            # 保留已有分镜提示词
            ff_prompt = sh.get("first_frame_prompt")
            lf_prompt = sh.get("last_frame_prompt")
            v_prompt = sh.get("video_prompt")
            if preserve_prompts and shot_no in old_shot_prompts:
                old_p = old_shot_prompts[shot_no]
                if "first_frame_prompt" in old_p:
                    ff_prompt = old_p["first_frame_prompt"]
                if "last_frame_prompt" in old_p:
                    lf_prompt = old_p["last_frame_prompt"]
                if "video_prompt" in old_p:
                    v_prompt = old_p["video_prompt"]

            shot = Shot(
                episode_id=episode.id,
                project_id=project_id,
                shot_no=shot_no,
                summary=sh.get("summary"),
                first_frame_prompt=ff_prompt,
                last_frame_prompt=lf_prompt,
                video_prompt=v_prompt,
                camera_size=sh.get("camera_size"),
                camera_angle=sh.get("camera_angle"),
                camera_movement=sh.get("camera_movement"),
                sort_order=shot_count,
            )
            session.add(shot)
            shot_count += 1

    session.commit()

    # 同步创建磁盘目录（commit 后实体才有 id，分镜才能查到 episode_no）
    for char in session.exec(select(Character).where(Character.project_id == project_id)).all():
        ensure_entity_dir(session, Character, char, project_id)
    for scene in session.exec(select(Scene).where(Scene.project_id == project_id)).all():
        ensure_entity_dir(session, Scene, scene, project_id)
    for prop in session.exec(select(Prop).where(Prop.project_id == project_id)).all():
        ensure_entity_dir(session, Prop, prop, project_id)
    for shot in session.exec(select(Shot).where(Shot.project_id == project_id)).all():
        ensure_entity_dir(session, Shot, shot, project_id)

    # 更新项目统计
    update_project_stats(session, project_id)

    return {
        "characters": char_count,
        "scenes": scene_count,
        "props": prop_count,
        "episodes": ep_count,
        "shots": shot_count,
    }


def _bind_shot_entities(
    session: Session,
    shot,
    character_names: list,
    scene_names: list,
    prop_names: list,
    char_name_to_id: dict,
    scene_name_to_id: dict,
    prop_name_to_id: dict,
) -> None:
    """将分镜与角色/场景/道具建立关联（多对多）。

    匹配规则：按名字精确匹配当前项目内已存在的实体。
    未匹配到的名字会被忽略（避免 LLM 编造或旧数据不一致导致写入失败）。
    """
    from app.models import ShotCharacter, ShotScene, ShotProp

    seen_char_ids: set[str] = set()
    for name in character_names:
        char_id = char_name_to_id.get(name)
        if char_id and char_id not in seen_char_ids:
            session.add(ShotCharacter(shot_id=shot.id, character_id=char_id))
            seen_char_ids.add(char_id)

    seen_scene_ids: set[str] = set()
    for name in scene_names:
        scene_id = scene_name_to_id.get(name)
        if scene_id and scene_id not in seen_scene_ids:
            session.add(ShotScene(shot_id=shot.id, scene_id=scene_id))
            seen_scene_ids.add(scene_id)

    seen_prop_ids: set[str] = set()
    for name in prop_names:
        prop_id = prop_name_to_id.get(name)
        if prop_id and prop_id not in seen_prop_ids:
            session.add(ShotProp(shot_id=shot.id, prop_id=prop_id))
            seen_prop_ids.add(prop_id)
