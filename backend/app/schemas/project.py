"""项目相关的 Pydantic Schema。"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    """新建项目请求。"""

    name: str = Field(..., min_length=1, max_length=200, description="项目名称")
    description: Optional[str] = Field(default=None, max_length=2000)
    cover_image: Optional[str] = Field(default=None, max_length=500)
    # 可选：自定义项目根目录（不传则自动生成）
    root_path: Optional[str] = Field(default=None, max_length=1000)


class ProjectUpdate(BaseModel):
    """更新项目请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    cover_image: Optional[str] = Field(default=None, max_length=500)
    status: Optional[str] = Field(default=None, pattern="^(active|archived)$")


class ProjectSummary(BaseModel):
    """项目摘要（列表页用）。"""

    id: str
    name: str
    description: Optional[str] = None
    cover_image: Optional[str] = None
    status: str
    character_count: int = 0
    scene_count: int = 0
    prop_count: int = 0
    episode_count: int = 0
    shot_count: int = 0
    created_at: str
    updated_at: str


class ProjectDetail(ProjectSummary):
    """项目详情。"""

    root_path: str
