"""剧本解析管线 — 提取阶段逻辑。

包含 Phase 1（角色/场景/道具提取）、Phase 2（章节划分）、Phase 3（分镜拆分）
以及规则化回退方案。
"""

from __future__ import annotations
import json
import logging
import re
from typing import Any
from app.pipelines._llm_utils import (
    _call_llm,
    _call_llm_stream,
    _extract_json,
    _load_template_content,
    _render_template,
)
logger = logging.getLogger(__name__)


# ============================================================
# Phase 1：并行提取角色/场景/道具
# ============================================================

async def _extract_characters(raw_text: str, project_id: str = "") -> list[dict]:
    """使用角色提取模板，从剧本中提取角色（支持流式输出）。"""
    template = _load_template_content("character")
    if not template:
        logger.warning("未找到角色提取模板，跳过")
        return []

    prompt = _render_template(template, script_text=raw_text)
    try:
        if project_id:
            resp = await _call_llm_stream(
                "你是一个专业的角色分析师，请严格按照要求的 JSON 格式输出。",
                prompt, project_id, "character",
            )
        else:
            resp = await _call_llm("你是一个专业的角色分析师，请严格按照要求的 JSON 格式输出。", prompt)
        logger.debug(f"[character] LLM 响应前 500 字: {resp[:500]}")
        result = _extract_json(resp)
        # 模板返回的是数组格式
        if isinstance(result, list):
            characters = result
        elif isinstance(result, dict):
            characters = result.get("characters", result.get("data", []))
        else:
            characters = []

        # 标准化字段
        normalized = []
        for c in characters:
            normalized.append({
                "name": c.get("name", "未命名"),
                "gender": c.get("gender", ""),
                "age": c.get("age", ""),
                "char_type": _map_role(c.get("role", c.get("char_type", "supporting"))),
                "description": c.get("description", ""),
                "settings": c.get("appearance", c.get("visualPrompt", c.get("settings", ""))),
            })
        return normalized
    except Exception as e:
        logger.error(f"角色提取失败: {e}")
        return []


async def _extract_scenes(raw_text: str, project_id: str = "") -> list[dict]:
    """使用场景提取模板，从剧本中提取场景（支持流式输出）。"""
    template = _load_template_content("scene")
    if not template:
        logger.warning("未找到场景提取模板，跳过")
        return []

    prompt = _render_template(template, script_text=raw_text)
    try:
        if project_id:
            resp = await _call_llm_stream(
                "你是一个专业的场景分析师，请严格按照要求的 JSON 格式输出。",
                prompt, project_id, "character",
            )
        else:
            resp = await _call_llm("你是一个专业的场景分析师，请严格按照要求的 JSON 格式输出。", prompt)
        result = _extract_json(resp)
        if isinstance(result, list):
            scenes = result
        elif isinstance(result, dict):
            scenes = result.get("scenes", result.get("data", []))
        else:
            scenes = []

        normalized = []
        for s in scenes:
            normalized.append({
                "name": s.get("name", "未命名"),
                "description": s.get("description", ""),
                "settings": s.get("visualPrompt", s.get("settings", "")),
                "camera_hint": s.get("cameraHint", s.get("camera_hint", "")),
            })
        return normalized
    except Exception as e:
        logger.error(f"场景提取失败: {e}")
        return []


async def _extract_props(raw_text: str, project_id: str = "") -> list[dict]:
    """使用道具提取模板，从剧本中提取道具（支持流式输出）。"""
    template = _load_template_content("prop")
    if not template:
        logger.warning("未找到道具提取模板，跳过")
        return []

    prompt = _render_template(template, script_text=raw_text)
    try:
        if project_id:
            resp = await _call_llm_stream(
                "你是一个专业的道具分析师，请严格按照要求的 JSON 格式输出。",
                prompt, project_id, "character",
            )
        else:
            resp = await _call_llm("你是一个专业的道具分析师，请严格按照要求的 JSON 格式输出。", prompt)
        logger.info(f"[prop] LLM 响应长度: {len(resp)}, 前 200 字: {resp[:200]}")
        result = _extract_json(resp)
        logger.info(f"[prop] 解析结果类型: {type(result).__name__}, 长度: {len(result) if isinstance(result, (list, dict)) else 'N/A'}")
        if isinstance(result, list):
            props = result
        elif isinstance(result, dict):
            props = result.get("props", result.get("data", []))
        else:
            props = []

        normalized = []
        for p in props:
            normalized.append({
                "name": p.get("name", "未命名"),
                "description": p.get("description", ""),
                "settings": p.get("visualPrompt", p.get("settings", "")),
            })
        return normalized
    except Exception as e:
        logger.warning(f"道具提取失败: {e}")
        return []


def _map_role(role: str) -> str:
    """将模板中的 role 字段映射为 char_type。"""
    role = str(role).strip()
    mapping = {
        "主角": "protagonist",
        "配角": "supporting",
        "群演": "extra",
        "protagonist": "protagonist",
        "supporting": "supporting",
        "extra": "extra",
    }
    return mapping.get(role, "supporting")


# ============================================================
# Phase 2：章节划分
# ============================================================

async def _extract_episodes(raw_text: str, project_id: str = "") -> list[dict]:
    """使用章节划分模板，将剧本拆分为剧集/章节（流式调用）。

    注意：章节划分模板需要 {{total_shots}}，但此时还没有分镜。
    我们先用规则化方式粗略估算分镜数，或直接传 0 让 LLM 自行判断。
    """
    template = _load_template_content("episode")
    if not template:
        logger.warning("未找到章节划分模板，使用规则解析")
        return _rule_based_episodes(raw_text)

    # 章节划分模板需要 total_shots，这里先粗略估算
    estimated_shots = max(1, len(raw_text) // 100)
    prompt = _render_template(template, script_text=raw_text, total_shots=str(estimated_shots))
    try:
        if project_id:
            resp = await _call_llm_stream(
                "你是一个专业的视频制作助手，请严格按照要求的 JSON 格式输出。",
                prompt, project_id, "episode",
            )
        else:
            resp = await _call_llm("你是一个专业的视频制作助手，请严格按照要求的 JSON 格式输出。", prompt)
        result = _extract_json(resp)

        # 模板返回格式: {"episodes": [{title, chapters: [{title, start, end, plot}]}]}
        episodes_data = result.get("episodes", []) if isinstance(result, dict) else []

        if not episodes_data:
            return _rule_based_episodes(raw_text)

        # 将章节格式转换为带 shots 的剧集格式
        episodes = []
        global_shot_no = 1
        for ep_idx, ep in enumerate(episodes_data):
            chapters = ep.get("chapters", [])
            shots = []
            for ch in chapters:
                start = ch.get("start", global_shot_no)
                end = ch.get("end", start)
                # 为每个章节创建一个分镜占位（具体分镜在 Phase 3 拆分）
                shots.append({
                    "shot_no": global_shot_no,
                    "summary": ch.get("plot", ch.get("title", "")),
                    "chapter_title": ch.get("title", ""),
                    "shot_start": start,
                    "shot_end": end,
                })
                global_shot_no += 1

            episodes.append({
                "episode_no": ep_idx + 1,
                "title": ep.get("title", f"第{ep_idx + 1}集"),
                "summary": "",
                "shots": shots,
            })

        return episodes
    except Exception as e:
        logger.error(f"章节划分失败，回退规则解析: {e}")
        return _rule_based_episodes(raw_text)


# ============================================================
# Phase 3：分镜拆分
# ============================================================

async def _extract_shots(
    raw_text: str,
    characters: list[dict],
    scenes: list[dict],
    props: list[dict],
    style_hint: str = "",
    project_id: str = "",
) -> list[dict]:
    """使用分镜拆分模板，将剧本逐段转换为分镜（流式调用）。

    返回格式：[{shot_no, summary, first_frame_prompt, last_frame_prompt, video_prompt, camera_size, camera_angle, camera_movement}, ...]
    """
    template = _load_template_content("shot")
    if not template:
        logger.warning("未找到分镜拆分模板，使用规则解析")
        return _rule_based_shots(raw_text)

    # 构建角色/场景/道具列表文本
    chars_text = "\n".join(
        f"- {c['name']}({c.get('char_type', '')}, {c.get('gender', '')}, {c.get('age', '')}): {c.get('description', '')}"
        for c in characters
    ) if characters else "（暂无）"

    scenes_text = "\n".join(
        f"- {s['name']}: {s.get('description', '')}"
        for s in scenes
    ) if scenes else "（暂无）"

    props_text = "\n".join(
        f"- {p['name']}: {p.get('description', '')}"
        for p in props
    ) if props else "（暂无）"

    prompt = _render_template(
        template,
        script_text=raw_text,
        characters=chars_text,
        scenes=scenes_text,
        props=props_text,
        style_hint=style_hint or "通用",
    )

    try:
        if project_id:
            resp = await _call_llm_stream(
                "你是一个专业的分镜拆分助手，请严格按照要求的格式输出。",
                prompt, project_id, "shot",
                temperature=0.2, json_mode=False, timeout_override=300,
            )
        else:
            resp = await _call_llm("你是一个专业的分镜拆分助手，请严格按照要求的格式输出。", prompt, temperature=0.2, json_mode=False, timeout_override=300)
        shots = _parse_shot_response(resp)
        if not shots:
            return _rule_based_shots(raw_text)
        return shots
    except Exception as e:
        logger.error(f"分镜拆分失败，回退规则解析: {e}")
        return _rule_based_shots(raw_text)


def _parse_shot_response(resp: str) -> list[dict]:
    """解析分镜模板的响应。

    分镜模板使用分隔符格式（_::-RECORD::-_），不是 JSON。
    也兼容 JSON 格式的响应。
    """
    # 尝试 JSON 格式
    try:
        result = _extract_json(resp)
        if isinstance(result, list):
            shots = result
        elif isinstance(result, dict):
            shots = result.get("shots", result.get("data", []))
        else:
            shots = []

        normalized = []
        for idx, s in enumerate(shots):
            shot = {
                "shot_no": s.get("shot_no", idx + 1),
                "summary": s.get("summary", s.get("description", "")),
                "first_frame_prompt": s.get("first_frame_prompt", s.get("firstFramePrompt", "")),
                "last_frame_prompt": s.get("last_frame_prompt", s.get("lastFramePrompt", "")),
                "video_prompt": s.get("video_prompt", s.get("videoPrompt", "")),
                "character_names": s.get("character_names", []),
                "scene_names": s.get("scene_names", []),
                "prop_names": s.get("prop_names", []),
            }
            # 如果没有显式关联字段，尝试从提示词中解析标记
            if not shot["character_names"]:
                shot["character_names"] = _extract_tagged_names(shot["first_frame_prompt"], tag_type="character")
            if not shot["scene_names"]:
                shot["scene_names"] = _extract_tagged_names(shot["first_frame_prompt"], tag_type="scene")
            if not shot["prop_names"]:
                shot["prop_names"] = _extract_tagged_names(shot["first_frame_prompt"], tag_type="prop")
            normalized.append(shot)
        return normalized
    except (json.JSONDecodeError, ValueError):
        pass

    # 分隔符格式解析
    if "_::-RECORD::-_" in resp or "_::-OUTPUT_START::-_" in resp:
        return _parse_delimiter_shots(resp)

    # 按段落拆分
    return _parse_paragraph_shots(resp)


def _parse_delimiter_shots(resp: str) -> list[dict]:
    """解析分隔符格式的分镜响应。

    支持新版 7 段格式（含首帧/尾帧/视频提示词）和旧版 4 段格式。
    同时提取关联的角色/场景/道具信息，供图生图 reference 注入使用。
    """
    # 提取 OUTPUT_START 和 OUTPUT_END 之间的内容
    start_marker = "_::-OUTPUT_START::-_"
    end_marker = "_::-OUTPUT_END::-_"
    record_sep = "_::-RECORD::-_"

    if start_marker in resp:
        resp = resp.split(start_marker, 1)[1]
    if end_marker in resp:
        resp = resp.split(end_marker, 1)[0]

    records = resp.split(record_sep)
    shots = []
    shot_no = 1
    for record in records:
        record = record.strip()
        if not record:
            continue

        # 解析各段落
        summary_parts = []
        first_frame = ""
        last_frame = ""
        video_prompt = ""
        visual_text = ""
        character_line = ""
        related_scene_line = ""

        lines = record.split("\n")
        current_section = ""
        section_content = []

        for line in lines:
            stripped = line.strip()
            # 检测段落标题
            if stripped.startswith("【首帧提示词】"):
                # 保存前一段
                if current_section == "visual":
                    visual_text = "\n".join(section_content).strip()
                elif current_section == "dialogue":
                    pass  # 对话不存入 summary
                elif current_section and section_content:
                    summary_parts.append("\n".join(section_content).strip())
                current_section = "first_frame"
                content_after = stripped[7:].strip()  # "【首帧提示词】" 长度 7
                section_content = [content_after] if content_after else []
            elif stripped.startswith("【尾帧提示词】"):
                if current_section == "first_frame":
                    first_frame = "\n".join(section_content).strip()
                elif current_section and section_content:
                    summary_parts.append("\n".join(section_content).strip())
                current_section = "last_frame"
                content_after = stripped[7:].strip()
                section_content = [content_after] if content_after else []
            elif stripped.startswith("【视频提示词】"):
                if current_section == "last_frame":
                    last_frame = "\n".join(section_content).strip()
                elif current_section and section_content:
                    summary_parts.append("\n".join(section_content).strip())
                current_section = "video_prompt"
                content_after = stripped[7:].strip()
                section_content = [content_after] if content_after else []
            elif stripped.startswith("【画面】"):
                if current_section == "summary":
                    summary_parts.append("\n".join(section_content).strip())
                current_section = "visual"
                content_after = stripped[4:].strip()
                section_content = [content_after] if content_after else []
            elif stripped.startswith("【对话/OS】") or stripped.startswith("【对话】"):
                if current_section == "visual":
                    visual_text = "\n".join(section_content).strip()
                elif current_section == "summary":
                    summary_parts.append("\n".join(section_content).strip())
                current_section = "dialogue"
                prefix_len = 6 if stripped.startswith("【对话/OS】") else 4
                content_after = stripped[prefix_len:].strip()
                section_content = [content_after] if content_after else []
            elif stripped.startswith("【原文对照】"):
                if current_section and section_content:
                    if current_section == "visual":
                        visual_text = "\n".join(section_content).strip()
                    elif current_section != "dialogue":
                        summary_parts.append("\n".join(section_content).strip())
                current_section = "summary"
                section_content = []
            elif stripped.startswith("出场人物"):
                if current_section == "summary":
                    summary_parts.append("\n".join(section_content).strip())
                current_section = "characters"
                # 提取 "出场人物：" 之后的内容
                if "：" in stripped:
                    character_line = stripped.split("：", 1)[1].strip()
                elif ":" in stripped:
                    character_line = stripped.split(":", 1)[1].strip()
                section_content = []
            elif stripped.startswith("【关联场景】"):
                if current_section == "video_prompt":
                    video_prompt = "\n".join(section_content).strip()
                elif current_section == "last_frame":
                    last_frame = "\n".join(section_content).strip()
                elif current_section == "first_frame":
                    first_frame = "\n".join(section_content).strip()
                elif current_section == "visual":
                    visual_text = "\n".join(section_content).strip()
                current_section = "related_scene"
                content_after = stripped[6:].strip()  # "【关联场景】" 长度 6
                related_scene_line = content_after
                section_content = []
            else:
                if current_section:
                    section_content.append(stripped)

        # 收集最后一段
        if current_section == "video_prompt" and section_content:
            video_prompt = "\n".join(section_content).strip()
        elif current_section == "last_frame" and section_content:
            last_frame = "\n".join(section_content).strip()
        elif current_section == "first_frame" and section_content:
            first_frame = "\n".join(section_content).strip()
        elif current_section == "visual" and section_content:
            visual_text = "\n".join(section_content).strip()

        # 如果没有独立的首帧提示词，用画面描述作为首帧
        if not first_frame and visual_text:
            first_frame = visual_text

        # summary 由原文对照 + 画面 + 对话组成
        full_summary = record.strip()

        # 提取关联实体名
        character_names = _parse_name_line(character_line)
        scene_names = _parse_name_line(related_scene_line)

        # 如果关联字段为空，从提示词标记中兜底解析
        all_prompt_text = f"{first_frame} {last_frame} {video_prompt}"
        if not character_names:
            character_names = _extract_tagged_names(all_prompt_text, tag_type="character")
        if not scene_names:
            scene_names = _extract_tagged_names(all_prompt_text, tag_type="scene")
        # 道具从标记中解析，但排除已被识别为角色/场景的名字
        prop_names = [
            name for name in _extract_tagged_names(all_prompt_text, tag_type="prop")
            if name not in character_names and name not in scene_names
        ]

        shots.append({
            "shot_no": shot_no,
            "summary": full_summary[:500],
            "first_frame_prompt": first_frame[:500] if first_frame else "",
            "last_frame_prompt": last_frame[:500] if last_frame else "",
            "video_prompt": video_prompt[:500] if video_prompt else "",
            "character_names": character_names,
            "scene_names": scene_names,
            "prop_names": prop_names,
        })
        shot_no += 1

    return shots


def _parse_paragraph_shots(resp: str) -> list[dict]:
    """按段落拆分非结构化的分镜响应。"""
    paragraphs = [p.strip() for p in resp.split("\n\n") if p.strip()]
    shots = []
    for idx, para in enumerate(paragraphs):
        if len(para) < 10:
            continue
        shots.append({
            "shot_no": idx + 1,
            "summary": para[:500],
            "first_frame_prompt": "",
            "last_frame_prompt": "",
            "video_prompt": "",
            "character_names": [],
            "scene_names": [],
            "prop_names": [],
        })
    return shots


# ============================================================
# 实体关联提取工具函数
# ============================================================

# 用于从提示词中解析【角色名】【场景名】【道具名】标记
_ENTITY_TAG_PATTERNS = {
    "character": re.compile(r"【([^】]+?)】"),
    "scene": re.compile(r"【([^】]+?)】"),
    "prop": re.compile(r"【([^】]+?)】"),
}


def _parse_name_line(line: str) -> list[str]:
    """解析顿号/逗号分隔的实体名列表，过滤掉占位符。"""
    if not line or line.strip() in ("无", "无", "暂无", "none", "-", "/"):
        return []
    # 按顿号或逗号拆分，并去除身份/状态括注
    names = re.split(r"[、,，]", line)
    result = []
    for name in names:
        name = name.strip()
        # 去除括注，例如 "张三(青年)" -> "张三"
        name = re.sub(r"[（(].*?[）)]", "", name).strip()
        if name and name not in ("无", "无", "暂无", "none", "-", "/"):
            result.append(name)
    return result


def _extract_tagged_names(text: str, tag_type: str = "character") -> list[str]:
    """从文本中提取被【】包裹的实体名。

    当前实现不区分类型标签，统一从【】中提取。后续如果提示词使用
    不同包裹方式（如【角色：张三】），可以按 tag_type 做更精细的过滤。
    """
    if not text:
        return []
    pattern = _ENTITY_TAG_PATTERNS.get(tag_type, _ENTITY_TAG_PATTERNS["character"])
    names = pattern.findall(text)
    # 去除括注并去重
    cleaned = []
    for name in names:
        name = re.sub(r"[（(].*?[）)]", "", name).strip()
        if name and name not in cleaned:
            cleaned.append(name)
    return cleaned


# ============================================================
# 规则化解析（回退方案）
# ============================================================

def _rule_based_episodes(raw_text: str) -> list[dict]:
    """规则化剧集拆分。"""
    episode_pattern = re.compile(r"第\s*(\d+)\s*[集章节回]|Episode\s*(\d+)", re.IGNORECASE)
    parts = episode_pattern.split(raw_text)
    episodes = []

    if len(parts) <= 1:
        episodes.append({
            "episode_no": 1,
            "title": "第1集",
            "summary": raw_text[:200] if raw_text else "",
            "shots": _rule_based_shots(raw_text),
        })
    else:
        idx = 0
        ep_no = 1
        while idx < len(parts):
            if idx == 0:
                if parts[idx].strip():
                    episodes.append({
                        "episode_no": ep_no,
                        "title": f"第{ep_no}集",
                        "summary": parts[idx].strip()[:200],
                        "shots": _rule_based_shots(parts[idx]),
                    })
                    ep_no += 1
                idx += 1
                continue

            num_str = parts[idx]
            idx += 1
            if idx < len(parts) and parts[idx] is not None:
                idx += 1
            body = parts[idx] if idx < len(parts) else ""
            idx += 1

            try:
                no = int(num_str) if num_str else ep_no
            except ValueError:
                no = ep_no

            episodes.append({
                "episode_no": no,
                "title": f"第{no}集",
                "summary": body.strip()[:200] if body else "",
                "shots": _rule_based_shots(body),
            })
            ep_no = max(ep_no, no + 1)

    return episodes


def _rule_based_shots(text: str) -> list[dict]:
    """规则化分镜拆分。"""
    if not text or not text.strip():
        return []

    shot_pattern = re.compile(r"(?:分镜|镜头|场景)\s*(\d+)")
    shot_parts = shot_pattern.split(text)
    shots = []

    if len(shot_parts) <= 1:
        if text.strip():
            shots.append({"shot_no": 1, "summary": text.strip()[:300]})
    else:
        idx = 0
        shot_no = 1
        while idx < len(shot_parts):
            if idx == 0:
                idx += 1
                continue
            no_str = shot_parts[idx]
            idx += 1
            body = shot_parts[idx] if idx < len(shot_parts) else ""
            idx += 1
            try:
                no = int(no_str) if no_str else shot_no
            except ValueError:
                no = shot_no
            if body.strip():
                shots.append({"shot_no": no, "summary": body.strip()[:300]})
            shot_no += 1

    return shots
