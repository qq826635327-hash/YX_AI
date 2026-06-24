"""业务实体（角色/场景/道具/剧集/分镜）Schema。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


# ============================================================
# 角色
# ============================================================

class CharacterCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    gender: Optional[str] = None
    age: Optional[str] = None
    char_type: str = Field(default="supporting", pattern="^(protagonist|supporting|extra)$")
    description: Optional[str] = None
    settings: Optional[str] = None


class CharacterUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    gender: Optional[str] = None
    age: Optional[str] = None
    char_type: Optional[str] = Field(default=None, pattern="^(protagonist|supporting|extra)$")
    description: Optional[str] = None
    settings: Optional[str] = None
    image_asset_id: Optional[str] = None
    gen_status: Optional[str] = None
    sort_order: Optional[int] = None


# ============================================================
# 场景
# ============================================================

class SceneCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    settings: Optional[str] = None
    camera_hint: Optional[str] = None


class SceneUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    settings: Optional[str] = None
    camera_hint: Optional[str] = None
    image_asset_id: Optional[str] = None
    gen_status: Optional[str] = None
    sort_order: Optional[int] = None


# ============================================================
# 道具
# ============================================================

class PropCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    settings: Optional[str] = None


class PropUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = None
    settings: Optional[str] = None
    image_asset_id: Optional[str] = None
    gen_status: Optional[str] = None
    sort_order: Optional[int] = None


# ============================================================
# 剧集
# ============================================================

class EpisodeCreate(BaseModel):
    episode_no: int = Field(..., ge=1)
    title: str = Field(..., min_length=1, max_length=200)
    summary: Optional[str] = None


class EpisodeUpdate(BaseModel):
    episode_no: Optional[int] = Field(default=None, ge=1)
    title: Optional[str] = Field(default=None, min_length=1, max_length=200)
    summary: Optional[str] = None
    sort_order: Optional[int] = None


# ============================================================
# 分镜
# ============================================================

class ShotCreate(BaseModel):
    shot_no: int = Field(..., ge=1)
    summary: Optional[str] = None
    first_frame_prompt: Optional[str] = None
    last_frame_prompt: Optional[str] = None
    video_prompt: Optional[str] = None
    camera_size: Optional[str] = None
    camera_angle: Optional[str] = None
    camera_movement: Optional[str] = None


class ShotUpdate(BaseModel):
    shot_no: Optional[int] = Field(default=None, ge=1)
    summary: Optional[str] = None
    first_frame_prompt: Optional[str] = None
    first_frame_asset_id: Optional[str] = None
    first_frame_status: Optional[str] = None
    last_frame_prompt: Optional[str] = None
    last_frame_asset_id: Optional[str] = None
    last_frame_status: Optional[str] = None
    video_prompt: Optional[str] = None
    video_asset_id: Optional[str] = None
    video_status: Optional[str] = None
    camera_size: Optional[str] = None
    camera_angle: Optional[str] = None
    camera_movement: Optional[str] = None
    sort_order: Optional[int] = None
