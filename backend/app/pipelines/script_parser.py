"""剧本解析管线。

Phase 1：占位实现，使用规则化拆分（按"集"/"分镜"关键词）。
Phase 2：接入 LLM 做结构化解析（characters/scenes/props/episodes/shots）。

设计原则：
- AI 解析是"初稿"，不是最终真理
- 所有字段都允许人工编辑
- 解析结果通过 WebSocket 推送进度
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.db import session_scope
from app.services.script_service import (
    mark_parse_failed,
    save_parsed_result,
    write_parsed_to_db,
)
from app.ws.routes import push_script_completed, push_script_failed, push_script_progress

logger = logging.getLogger(__name__)


# ============================================================
# Phase 1：规则化解析（占位）
# ============================================================

SYSTEM_PROMPT = """你是一名资深剧本拆解助手。请仔细阅读用户提供的剧本，并输出一个严格符合以下 JSON Schema 的结构化解析结果。

输出格式要求：
1. 只输出 JSON，不要任何解释、Markdown 代码块标记或额外文字。
2. JSON 必须能被 Python json.loads 直接解析。
3. 所有字段必须存在，没有值时使用空字符串 ""、空列表 [] 或 0。

Schema：
{
  "characters": [
    {
      "name": "角色名（2-8 字）",
      "char_type": "protagonist / supporting / extra",
      "description": "角色外貌、性格、服装等描述",
      "settings": "Stable Diffusion 提示词风格的形象设定，用于后续生图"
    }
  ],
  "scenes": [
    {
      "name": "场景名（如：古城街道）",
      "description": "场景描述",
      "settings": "Stable Diffusion 提示词风格的场景设定"
    }
  ],
  "props": [
    {
      "name": "道具名",
      "description": "道具描述",
      "settings": "Stable Diffusion 提示词风格的道具设定"
    }
  ],
  "episodes": [
    {
      "episode_no": 1,
      "title": "第1集",
      "summary": "本集剧情摘要（200 字以内）",
      "shots": [
        {
          "shot_no": 1,
          "summary": "分镜内容摘要（300 字以内）",
          "first_frame_prompt": "首帧生成提示词，含主体、场景、光影、风格",
          "last_frame_prompt": "尾帧生成提示词，可选",
          "video_prompt": "视频生成提示词，可选"
        }
      ]
    }
  ]
}

解析规则：
- 按"第 X 集"、"Episode X"、"集"等标记拆分剧集；如果没有明确分集，则整体作为 1 集。
- 每集内部按"分镜 X"、"镜头 X"、"场景 X"拆分；如果没有标记，按段落或场景切换拆分。
- 角色名抽取要准确，避免把普通名词、地名误判为角色。
- 场景和道具不需要强行填充，确实没有时返回空列表。
- 提示词应包含英文关键词，便于后续调用图像生成 API。
"""


def _rule_based_parse(raw_text: str) -> dict[str, Any]:
    """规则化解析：从剧本文本中粗略提取结构。

    这只是 Phase 1 的占位实现，用于在没有 LLM 时也能产生基本结构。
    Phase 2 会替换为 LLM 解析。
    """
    characters: list[dict] = []
    scenes: list[dict] = []
    props: list[dict] = []
    episodes: list[dict] = []

    # 按集拆分（匹配"第X集"、"第X章"、"Episode X"）
    episode_pattern = re.compile(r"第\s*(\d+)\s*[集章节回]|Episode\s*(\d+)", re.IGNORECASE)
    parts = episode_pattern.split(raw_text)

    # parts 结构：[前言, 编号1, None/编号2, 正文1, 编号3, None/编号4, 正文2, ...]
    if len(parts) <= 1:
        # 没有集分隔，整体作为第 1 集
        episodes.append({
            "episode_no": 1,
            "title": "第1集",
            "summary": raw_text[:200] if raw_text else "",
            "shots": _split_shots(raw_text),
        })
    else:
        idx = 0
        ep_no = 1
        while idx < len(parts):
            if idx == 0:
                # 前言部分（如果有内容）
                if parts[idx].strip():
                    episodes.append({
                        "episode_no": ep_no,
                        "title": f"第{ep_no}集",
                        "summary": parts[idx].strip()[:200],
                        "shots": _split_shots(parts[idx]),
                    })
                    ep_no += 1
                idx += 1
                continue

            # 编号
            num_str = parts[idx]
            idx += 1
            # 第二个分组（可能为 None）
            if idx < len(parts) and parts[idx] is not None:
                idx += 1
            # 正文
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
                "shots": _split_shots(body),
            })
            ep_no = max(ep_no, no + 1)

    # 从全文粗略抽取角色名（中文2-4字 + "："开头的行）
    char_pattern = re.compile(r"^[\u4e00-\u9fa5]{2,4}[\s]*[：:]", re.MULTILINE)
    seen_names = set()
    for m in char_pattern.finditer(raw_text):
        name = m.group().rstrip("：:").strip()
        if name and name not in seen_names and len(name) <= 6:
            seen_names.add(name)
            characters.append({
                "name": name,
                "char_type": "supporting",
                "description": "",
                "settings": "",
            })

    # 场景与道具在 Phase 1 留空，等 Phase 2 LLM 提取
    return {
        "characters": characters[:20],  # 限制数量
        "scenes": scenes,
        "props": props,
        "episodes": episodes,
    }


def _split_shots(text: str) -> list[dict]:
    """粗略拆分分镜。"""
    if not text or not text.strip():
        return []
    # 匹配"分镜X"、"镜头X"、"场景X"
    shot_pattern = re.compile(r"(?:分镜|镜头|场景)\s*(\d+)")
    shot_parts = shot_pattern.split(text)

    shots: list[dict] = []
    if len(shot_parts) <= 1:
        # 没有分镜标记，整段作为 1 个分镜
        if text.strip():
            shots.append({
                "shot_no": 1,
                "summary": text.strip()[:300],
            })
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
                shots.append({
                    "shot_no": no,
                    "summary": body.strip()[:300],
                })
            shot_no += 1
    return shots


# ============================================================
# Phase 2：LLM 解析
# ============================================================

async def _llm_parse(raw_text: str) -> dict[str, Any]:
    """调用 LLM 做结构化解析。

    1. 构造 system prompt（角色/场景/道具/剧集/分镜抽取规范）
    2. 调用 OpenAI 兼容 API（JSON mode）
    3. 校验返回的 JSON 结构
    4. 返回标准化结果
    """
    settings = get_settings()
    if not settings.llm.enabled or not settings.llm.api_key:
        # 未配置 LLM，回退到规则解析
        return _rule_based_parse(raw_text)

    try:
        async with httpx.AsyncClient(timeout=settings.llm.timeout) as client:
            resp = await client.post(
                f"{settings.llm.base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.llm.api_key}"},
                json={
                    "model": settings.llm.model,
                    "messages": [
                        {"role": "system", "content": SYSTEM_PROMPT},
                        {"role": "user", "content": raw_text},
                    ],
                    "temperature": 0.3,
                    "response_format": {"type": "json_object"},
                },
            )
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

        # 标准化：确保必要键存在
        normalized = {
            "characters": parsed.get("characters", []) or [],
            "scenes": parsed.get("scenes", []) or [],
            "props": parsed.get("props", []) or [],
            "episodes": parsed.get("episodes", []) or [],
        }

        # 兜底：如果 LLM 没拆出剧集，整体作为第 1 集
        if not normalized["episodes"]:
            normalized["episodes"] = [{
                "episode_no": 1,
                "title": "第1集",
                "summary": raw_text[:200] if raw_text else "",
                "shots": _split_shots(raw_text),
            }]

        # 为每个分镜补充默认 shot_no
        for ep in normalized["episodes"]:
            for idx, sh in enumerate(ep.get("shots", []) or []):
                sh.setdefault("shot_no", idx + 1)

        return normalized

    except Exception as e:
        # LLM 调用失败时回退到规则解析，保证流程不中断
        logger.warning(f"LLM 解析失败，回退到规则解析: {e}")
        return _rule_based_parse(raw_text)


# ============================================================
# 异步解析入口（被 BackgroundTasks 调用）
# ============================================================

async def parse_script_async(script_id: str, project_id: str) -> None:
    """异步执行剧本解析（后台任务）。

    流程：
    1. 读取剧本文本
    2. 推送 script.parsing 进度
    3. 调用解析（LLM 或规则）
    4. 校验与补全
    5. 写入业务表
    6. 保存解析结果到 ScriptDocument
    7. 推送 script.completed
    """
    try:
        await push_script_progress(project_id, "reading", message="正在读取剧本")

        from app.models import ScriptDocument

        with session_scope() as session:
            doc = session.get(ScriptDocument, script_id)
            if not doc:
                await push_script_failed(project_id, "剧本记录不存在")
                return
            raw_text = doc.raw_text

        await push_script_progress(project_id, "parsing", message="正在解析剧本结构")

        # 执行解析
        parsed = await _llm_parse(raw_text)

        await push_script_progress(project_id, "writing", message="正在写入数据库")

        # 写入业务表
        with session_scope() as session:
            stats = write_parsed_to_db(session, project_id, parsed)
            save_parsed_result(session, script_id, parsed)

        await push_script_completed(
            project_id,
            message="剧本解析完成",
            stats=stats,
        )

    except Exception as e:
        logger.exception(f"剧本解析失败 (script_id={script_id}): {e}")
        with session_scope() as session:
            mark_parse_failed(session, script_id, str(e))
        await push_script_failed(project_id, str(e))
