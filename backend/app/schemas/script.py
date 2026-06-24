"""剧本相关 Schema。"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ScriptUpdate(BaseModel):
    """更新剧本文本。"""

    raw_text: str = Field(..., description="原始剧本文本")


class ScriptParseRequest(BaseModel):
    """触发剧本解析。"""

    # 是否强制重新解析（已有结果时）
    force: bool = Field(default=False)
    # 可选指定 LLM Provider（不传则用默认）
    llm_provider_id: Optional[str] = None
    # 重新解析时是否保留已有提示词（settings 字段）
    preserve_prompts: bool = Field(
        default=False,
        description="为 True 时，已有实体的提示词（settings）不会被新解析结果覆盖",
    )
    # 解析目标：控制哪些实体需要提取
    parse_targets: list[str] = Field(
        default=["characters", "scenes", "props", "episodes"],
        description="解析目标列表，可选值: characters, scenes, props, episodes",
    )


class ParsedCharacter(BaseModel):
    name: str
    char_type: str = "supporting"
    description: Optional[str] = None
    settings: Optional[str] = None


class ParsedScene(BaseModel):
    name: str
    description: Optional[str] = None
    settings: Optional[str] = None


class ParsedProp(BaseModel):
    name: str
    description: Optional[str] = None
    settings: Optional[str] = None


class ParsedShot(BaseModel):
    shot_no: int
    summary: Optional[str] = None
    first_frame_prompt: Optional[str] = None
    last_frame_prompt: Optional[str] = None
    video_prompt: Optional[str] = None


class ParsedEpisode(BaseModel):
    episode_no: int
    title: str
    summary: Optional[str] = None
    shots: list[ParsedShot] = Field(default_factory=list)


class ParsedResult(BaseModel):
    """剧本解析结果。"""

    characters: list[ParsedCharacter] = Field(default_factory=list)
    scenes: list[ParsedScene] = Field(default_factory=list)
    props: list[ParsedProp] = Field(default_factory=list)
    episodes: list[ParsedEpisode] = Field(default_factory=list)


class ScriptView(BaseModel):
    """剧本视图。"""

    id: str
    project_id: str
    raw_text: str
    version: int
    parse_status: str
    parse_error: Optional[str] = None
    parsed_at: Optional[str] = None
    parsed_result: Optional[dict[str, Any]] = None
    current_stage: Optional[str] = None
    completed_stages: Optional[list[dict[str, Any]]] = None
    created_at: str
    updated_at: str
