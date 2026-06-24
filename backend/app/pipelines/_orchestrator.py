"""剧本解析管线 — 主编排入口。

串联 Phase 1/2/3 提取阶段，管理进度/WS 推送/错误处理。
"""
from __future__ import annotations

import logging

from app.db import session_scope
from app.pipelines._llm_utils import (
    _find_text_llm_config,
    _update_task_progress,
    _update_task_status,
)
from app.pipelines._extraction_stages import (
    _extract_characters,
    _extract_scenes,
    _extract_props,
    _extract_episodes,
    _extract_shots,
    _rule_based_episodes,
    _rule_based_shots,
)
from app.services.script_service import (
    mark_parse_failed,
    save_parsed_result,
    write_entities_to_db,
    write_episodes_to_db,
    write_parsed_to_db,
    save_pre_parse_snapshot,
    restore_from_snapshot,
)
from app.ws.routes import (
    push_script_completed,
    push_script_failed,
    push_script_progress,
    push_script_stream,
    push_script_stage_done,
)

logger = logging.getLogger(__name__)


# ============================================================
# 主解析入口
# ============================================================

async def parse_script_async(script_id: str, project_id: str, preserve_prompts: bool = False, parse_targets: list[str] | None = None) -> None:
    """异步执行剧本解析（后台任务）。

    流程：
    1. 读取剧本文本
    2. 顺序提取角色/场景/道具（流式输出）— 仅当 parse_targets 包含对应项
    3. 章节划分（流式，推送 LLM 输出）— 仅当 parse_targets 包含 episodes
    4. 分镜拆分（流式，推送 LLM 输出）— 仅当 parse_targets 包含 episodes
    5. 合并结果，写入业务表
    6. 保存解析结果到 ScriptDocument
    7. 推送完成通知

    每个阶段开始推送 script.parsing，完成推送 script.stage_done。
    串行阶段（episode/shot）额外推送 script.stream（LLM 流式输出）。

    Args:
        script_id: 剧本文档 ID
        project_id: 项目 ID
        preserve_prompts: 为 True 时，已有实体的提示词不会被新解析结果覆盖
        parse_targets: 解析目标列表，可选值: characters, scenes, props, episodes
    """
    # 默认全选
    if parse_targets is None:
        parse_targets = ["characters", "scenes", "props", "episodes"]
    targets = set(parse_targets)

    def _check_cancelled() -> bool:
        """检查是否已被用户取消（parse_status == 'cancelled'）。"""
        with session_scope() as s:
            doc = s.get(ScriptDocument, script_id)
            return doc is not None and doc.parse_status == "cancelled"

    # 已完成的步骤列表，随解析推进逐步追加，供前端恢复状态
    completed_stages: list[dict] = []

    def _update_script_stage(stage: str | None, done_stages: list[dict] | None = None) -> None:
        """更新 ScriptDocument 的 current_stage 和 completed_stages，供前端恢复进度。"""
        with session_scope() as s:
            doc = s.get(ScriptDocument, script_id)
            if doc:
                if stage is not None:
                    doc.current_stage = stage
                if done_stages is not None:
                    doc.completed_stages = done_stages
                s.add(doc)
                s.commit()

    # 创建任务中心记录
    from app.models import GenerationTask
    from app.ws.routes import push_task_created, push_task_progress, push_task_completed, push_task_failed
    from datetime import datetime, timezone

    task_id = ""
    with session_scope() as session:
        task = GenerationTask(
            project_id=project_id,
            target_type="script_parse",
            target_id=script_id,
            provider_type="api",
            input_payload={"preserve_prompts": preserve_prompts, "parse_targets": parse_targets},
            status="running",
            progress=0,
            started_at=datetime.now(timezone.utc),
        )
        session.add(task)
        session.commit()
        session.refresh(task)
        task_id = task.id
    await push_task_created(task_id, project_id, target_type="script_parse")

    # 解析阶段到进度的映射
    STAGE_PROGRESS = {"reading": 5, "character": 25, "episode": 50, "shot": 75, "writing": 95}

    try:
        from app.models import ScriptDocument

        with session_scope() as session:
            doc = session.get(ScriptDocument, script_id)
            if not doc:
                _update_task_status(task_id, "failed", error_message="剧本记录不存在")
                await push_task_failed(task_id, "剧本记录不存在", target_type="script_parse")
                await push_script_failed(project_id, "剧本记录不存在")
                return
            raw_text = doc.raw_text

        if not raw_text or not raw_text.strip():
            _update_task_status(task_id, "failed", error_message="剧本内容为空")
            await push_task_failed(task_id, "剧本内容为空", target_type="script_parse")
            await push_script_failed(project_id, "剧本内容为空")
            return

        # reading 阶段瞬间完成，直接标记 done
        completed_stages.append({"stage": "reading", "summary": "读取完成"})
        _update_script_stage("reading", completed_stages)

        # 解析前保存当前实体快照，用于取消时恢复
        with session_scope() as session:
            save_pre_parse_snapshot(session, project_id, script_id)

        has_llm = _find_text_llm_config() is not None

        # 获取项目画风设置（从画风预置数据库读取 description）
        style_hint = ""
        from app.models import Project
        with session_scope() as session:
            project = session.get(Project, project_id)
            if project and project.style_preset:
                # 优先从画风预置表查找
                from app.services.style_preset_service import get_preset_by_title, list_presets
                preset = get_preset_by_title(session, project.style_preset)
                if preset:
                    style_hint = preset.description
                else:
                    # 兼容旧值：style_preset 可能存的是旧 key（如 anime/3d/ink）
                    old_style_map = {
                        "anime": "二次元动漫风格",
                        "3d": "3D渲染风格",
                        "ink": "水墨插画风格",
                        "realistic": "写实风格",
                        "comic": "漫画风格",
                        "cinematic": "电影级写实质感，柔和电影光影，自然景深虚化，极致细节纹理，丰富色彩层次，8K超高清",
                        "default": "通用",
                    }
                    style_hint = old_style_map.get(project.style_preset, project.style_preset)

        # ---- Phase 1：顺序提取角色/场景/道具（流式输出） ----
        need_entities = bool(targets & {"characters", "scenes", "props"})
        if need_entities and has_llm:
            await push_script_progress(project_id, "character", message="正在提取角色", completed_stages=completed_stages)
            _update_script_stage("character", completed_stages)
            _update_task_progress(task_id, STAGE_PROGRESS.get("character", 25))

            characters = []
            scenes = []
            props = []

            if "characters" in targets:
                characters = await _extract_characters(raw_text, project_id=project_id)

            # 场景提取（流式输出继续追加到 character 阶段）
            if "scenes" in targets:
                await push_script_stream(project_id, "character", "\n\n--- 场景提取 ---\n\n")
                scenes = await _extract_scenes(raw_text, project_id=project_id)

            # 道具提取（流式输出继续追加到 character 阶段）
            if "props" in targets:
                await push_script_stream(project_id, "character", "\n\n--- 道具提取 ---\n\n")
                props = await _extract_props(raw_text, project_id=project_id)
        elif not need_entities:
            await push_script_progress(project_id, "character", message="已跳过角色/场景/道具提取", completed_stages=completed_stages)
            characters = []
            scenes = []
            props = []
        else:
            await push_script_progress(project_id, "character", message="未配置文本模型，跳过角色/场景/道具提取", completed_stages=completed_stages)
            characters = []
            scenes = []
            props = []

        logger.info(f"提取完成: 角色={len(characters)}, 场景={len(scenes)}, 道具={len(props)}")

        # 立即将角色/场景/道具写入 DB，前端可尽早看到数据
        with session_scope() as session:
            entity_stats = write_entities_to_db(session, project_id, characters, scenes, props, preserve_prompts=preserve_prompts, targets=targets)
        logger.info(f"角色/场景/道具已写入DB: {entity_stats}")

        completed_stages.append({"stage": "character", "summary": f"角色 {len(characters)} 个，场景 {len(scenes)} 个，道具 {len(props)} 个"})
        _update_script_stage("character", completed_stages)
        await push_script_stage_done(project_id, "character", summary=f"角色 {len(characters)} 个，场景 {len(scenes)} 个，道具 {len(props)} 个", completed_stages=completed_stages)

        # 检查是否被取消
        if _check_cancelled():
            logger.info("检测到取消信号，恢复数据并退出")
            with session_scope() as session:
                restore_from_snapshot(session, project_id, script_id)
            _update_task_status(task_id, "failed", error_message="用户取消解析")
            await push_task_failed(task_id, "用户取消解析", target_type="script_parse")
            await push_script_failed(project_id, "用户取消解析")
            return

        # ---- Phase 2：章节划分（流式） ----
        need_episodes = "episodes" in targets
        if need_episodes and has_llm:
            await push_script_progress(project_id, "episode", message="正在划分章节", completed_stages=completed_stages)
            _update_script_stage("episode", completed_stages)
            _update_task_progress(task_id, STAGE_PROGRESS.get("episode", 50))
            episodes = await _extract_episodes(raw_text, project_id=project_id)
        elif need_episodes:
            episodes = _rule_based_episodes(raw_text)
        else:
            await push_script_progress(project_id, "episode", message="已跳过剧集结构提取", completed_stages=completed_stages)
            episodes = []

        logger.info(f"章节划分完成: 剧集={len(episodes)}")
        completed_stages.append({"stage": "episode", "summary": f"共 {len(episodes)} 集"})
        _update_script_stage("episode", completed_stages)
        await push_script_stage_done(project_id, "episode", summary=f"共 {len(episodes)} 集", completed_stages=completed_stages)

        # 检查是否被取消
        if _check_cancelled():
            logger.info("检测到取消信号，恢复数据并退出")
            with session_scope() as session:
                restore_from_snapshot(session, project_id, script_id)
            _update_task_status(task_id, "failed", error_message="用户取消解析")
            await push_task_failed(task_id, "用户取消解析", target_type="script_parse")
            await push_script_failed(project_id, "用户取消解析")
            return

        # ---- Phase 3：分镜拆分（流式） ----
        if need_episodes and has_llm:
            await push_script_progress(project_id, "shot", message="正在拆分分镜", completed_stages=completed_stages)
            _update_script_stage("shot", completed_stages)
            _update_task_progress(task_id, STAGE_PROGRESS.get("shot", 75))
            flat_shots = await _extract_shots(raw_text, characters, scenes, props, style_hint=style_hint, project_id=project_id)
        elif need_episodes:
            flat_shots = _rule_based_shots(raw_text)
        else:
            await push_script_progress(project_id, "shot", message="已跳过分镜拆分", completed_stages=completed_stages)
            flat_shots = []

        logger.info(f"分镜拆分完成: 分镜={len(flat_shots)}")
        completed_stages.append({"stage": "shot", "summary": f"共 {len(flat_shots)} 个分镜"})
        _update_script_stage("shot", completed_stages)
        await push_script_stage_done(project_id, "shot", summary=f"共 {len(flat_shots)} 个分镜", completed_stages=completed_stages)

        # ---- 合并：将分镜分配到剧集中 ----
        await push_script_progress(project_id, "writing", message="正在写入数据库", completed_stages=completed_stages)
        _update_script_stage("writing", completed_stages)
        _update_task_progress(task_id, STAGE_PROGRESS.get("writing", 95))

        if episodes and flat_shots:
            # 如果剧集有章节信息（shot_start/shot_end），按范围分配
            has_chapter_info = any(
                sh.get("shot_start") is not None
                for ep in episodes
                for sh in ep.get("shots", [])
            )

            if has_chapter_info:
                # 将 flat_shots 分配到对应的章节中
                for ep in episodes:
                    chapter_shots = []
                    for ch in ep.get("shots", []):
                        start = ch.get("shot_start", 1)
                        end = ch.get("shot_end", start)
                        # 找到 shot_no 在 [start, end] 范围内的分镜
                        for s in flat_shots:
                            if start <= s.get("shot_no", 0) <= end:
                                chapter_shots.append(s)
                    # 用实际分镜替换章节占位
                    ep["shots"] = chapter_shots if chapter_shots else [ch]
            else:
                # 没有章节范围信息，均匀分配分镜到剧集中
                total_shots = len(flat_shots)
                total_episodes = len(episodes)
                shots_per_ep = max(1, total_shots // total_episodes)
                for i, ep in enumerate(episodes):
                    start_idx = i * shots_per_ep
                    end_idx = start_idx + shots_per_ep if i < total_episodes - 1 else total_shots
                    ep["shots"] = flat_shots[start_idx:end_idx]
        elif episodes and not flat_shots:
            # 有剧集但没有分镜，保持剧集结构
            pass
        elif not episodes and flat_shots:
            # 没有剧集但有分镜，整体作为第 1 集
            episodes = [{
                "episode_no": 1,
                "title": "第1集",
                "summary": raw_text[:200] if raw_text else "",
                "shots": flat_shots,
            }]
        else:
            # 都没有，用规则解析兜底
            episodes = _rule_based_episodes(raw_text)

        # 为每个分镜补充 shot_no
        for ep in episodes:
            for idx, sh in enumerate(ep.get("shots", []) or []):
                sh.setdefault("shot_no", idx + 1)

        # 组装最终结果
        parsed = {
            "characters": characters,
            "scenes": scenes,
            "props": props,
            "episodes": episodes,
        }

        # 写入剧集和分镜（角色/场景/道具已在 Phase 1 完成后写入）
        with session_scope() as session:
            ep_stats = write_episodes_to_db(session, project_id, episodes, preserve_prompts=preserve_prompts, skip_if_empty=not need_episodes)
            save_parsed_result(session, script_id, parsed)

        stats = {**entity_stats, **ep_stats}

        completed_stages.append({"stage": "writing", "summary": "写入完成"})
        _update_script_stage(None, completed_stages)  # 清空 current_stage，标记全部完成
        await push_script_stage_done(project_id, "writing", summary="写入完成", completed_stages=completed_stages)

        # 更新任务中心：成功
        _update_task_status(task_id, "succeeded", 100)
        await push_task_completed(task_id, target_type="script_parse")

        await push_script_completed(
            project_id,
            message="剧本解析完成",
            stats=stats,
        )

    except Exception as e:
        logger.exception(f"剧本解析失败 (script_id={script_id}): {e}")
        with session_scope() as session:
            mark_parse_failed(session, script_id, str(e))
        # 清空进度状态
        _update_script_stage(None, None)

        # 更新任务中心：失败
        _update_task_status(task_id, "failed", error_message=str(e))
        await push_task_failed(task_id, str(e), target_type="script_parse")

        await push_script_failed(project_id, str(e))
